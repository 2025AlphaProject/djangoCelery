import anthropic

from .tour_api import *
import ast
from usr.models import User
from .ai_models.ai_service import get_ai_response
from .ai_models import claude_ai, deepseek_ai, gemini_ai
from config.settings import APP_LOGGER
import logging
logger = logging.getLogger(APP_LOGGER)



class AiTourRecommender:
    AI_MODEL = gemini_ai.GeminiModel()
    SYSTEM_TEXT = """
    너는 여행사 투어 가이드야. 하루치 여행 코스를 여러가지 짜려고 해. 아래의 예시 답변을 보고 알맞게 답변해줘. 반드시 부가 설명없이 아래 답변 처럼 제시를 해야해!!
    참고로 mapX는 경도 좌표를, mapY는 위도 좌표를, name은 장소 이름을 뜻해.
[
   [
      {
         "id":"0",
         "name":"A",
         "mapX":"126",
         "mapY":"37.2"
      },
      {
         "id":"1",
         "name":"B",
         "mapX":"125",
         "mapY":"37.5"
      }
   ],
   [
      {
         "id":"7",
         "name":"C",
         "mapX":"111.5",
         "mapY":"37.1"
      }
   ]
]
    위에서 예시 답변을 보면 알겠지만, 각 여행 코스에 해당하는 장소들 묶음은 하나의 리스트, 하나의 리스트 안에 있는 장소들은 딕셔너리 형태, 모든 여행 코스들은 리스트에 담아서 출력할거야. 또한, 반드시 이스케이프 코드는 제거해줘야해.
    """
    CONTENT_TEXT = """
    \n이 리스트에는 각각 관광, 레포츠, 문화, 쇼핑 시설 정보가 들어있는 리스트가 있어. 각 시설 리스트에서 한국에서 유명한 시설들만 적절히 골라서 여행 코스를 구성해줘.
    장소들을 골랐다면, 각 장소들이 위도, 경도를 기준으로 이동하기 가장 적합하도록 장소 순서를 다시 재배치해줘.
    각 여행코스 리스트 안의 index 순서가 여행 순서야.
    """
    def __init__(self, model='claude-3-7-sonnet-20250219', ai_service_key=None, tour_service_key=None):
        self.__model = model # ai_model 등록
        self.__ai_service_key = self.set_ai_service_key(ai_service_key) # ai_api service key 등록
        self.__tour_service_key = self.set_tour_service_key(tour_service_key) # tour_service key 등록
        self.__place_list = [] # 장소 리스트 입니다.
        self.__additional_comment = '' # 추가 프롬프팅 텍스트입니다.

    def set_ai_service_key(self, service_key):
        self.__ai_service_key = service_key
        return self.__ai_service_key

    def set_tour_service_key(self, tour_service_key):
        self.__tour_service_key = tour_service_key
        return self.__tour_service_key

    def __get_area_based_tour_list(self, areaCode, contentTypeId, arrange, sigunguCode=None):
        tour = TourApi(MobileOS=MobileOS.ANDROID, MobileApp='AiTourRecommender', service_key=self.__tour_service_key)
        data = {
            'areaCode': areaCode.value if isinstance(areaCode, Enum) else areaCode,
            'contentTypeId': contentTypeId.value if isinstance(contentTypeId, Enum) else contentTypeId,
            'arrange': arrange.value if isinstance(arrange, Enum) else arrange,
        }
        st_index = len(self.__place_list)
        if sigunguCode is not None:
            for each in sigunguCode:
                data['sigunguCode'] = each
                self.__place_list += tour.get_area_based_list(**data)
        else:
            self.__place_list += tour.get_area_based_list(**data) # result 요소에는 Area 객체가 들어옵니다.
        list = []
        for i in range(st_index, len(self.__place_list)):
            each = self.__place_list[i]
            list.append({
                'id': i,
                'name': each.get_title(),
                'mapX': each.get_mapX(),
                'mapY': each.get_mapY(),
            })
        return list # 정보 구분 위해 리스트로 감쌉니다.

    def __get_location_based_tour_list(self, mapX, mapY, radius, **kwargs):
        """
        위치기반 데이터 가져오기
        :return:
        """
        tour = TourApi(MobileOS=MobileOS.ANDROID, MobileApp='AiTourRecommender', service_key=self.__tour_service_key)
        data = {
            'mapX': mapX,
            'mapY': mapY,
            'radius': radius,
        }
        for each in kwargs.keys():
            data[each] = kwargs[each].value if isinstance(kwargs[each], Enum) else kwargs[each]
        self.__place_list = tour.get_location_based_list(**data) # result 요소에는 Area 객체가 들어옵니다.
        list = []
        for i in range(len(self.__place_list)):
            each = self.__place_list[i]
            list.append({
                'id': i,
                'name': each.get_title(),
                'mapX': each.get_mapX(),
                'mapY': each.get_mapY(),
            })

        return list


    def __get_ai_comment(self, place_list):
        """
        실제 ai 코멘트를 받는 역할을 합니다.
        :return:
        """
        self.AI_MODEL.ai_service_key = self.__ai_service_key
        return get_ai_response(self.AI_MODEL, self.SYSTEM_TEXT, str(place_list) + self.CONTENT_TEXT + self.__additional_comment)

    def __get_personal_comment(self, user_id):
        """
        Ai 프롬프팅에 넣을 사용자 맞춤 정보를 설정합니다.
        """
        user = None
        try:
            user = User.objects.get(sub=user_id)
        except User.DoesNotExist:
            return ""
        if user is not None:
            return f"""
            사용자의 나이대와 성별 정보는 다음과 같아. 다음 정보를 보고 나이대와 성별에 맞게 장소 추천을 해줘.
            참고로 나이대는 예를들어서 1세이상 9세 이하면 1~9로 표기돼.\n
            나이대: {user.age_range}, 성별: {user.gender}
            """

    def __get_days_comment(self):
        return f"여행 코스는 반드시 {self.days}가지 경우로 구성했으면 좋겠고, 한 여행 코스에는 최소 5가지 장소가 들어갔으면 좋겠고, 같은 장소가 반복되면 안돼.\n"




    def get_recommended_tour_list_based_area(self, user_id, days, areaCode=AreaCode.SEOUL, arrange=Arrange.TITLE_IMAGE, sigunguCode=None):
        """

        :return: 파이썬 리스트를 반환합니다.
        """
        places = []
        self.days = days
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.GWANGWANGJI, arrange, sigunguCode)) # 관광지 정보 추가
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.LEIPORTS, arrange, sigunguCode)) # 레포츠 정보 추가
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.MUNHWASISUL, arrange, sigunguCode)) # 문화 시설
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.SHOPPING, arrange, sigunguCode)) # 쇼핑 정보
        # places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.SUKBAK, arrange, sigunguCode))  # 숙박 정보
        self.__additional_comment = self.__get_days_comment()
        self.__additional_comment += self.__get_personal_comment(user_id)
        comment = self.__get_ai_comment(places)
        try:
            # 문자열을 리스트로 변환
            list = []
            tour_list = ast.literal_eval(comment)
            for i in range(len(tour_list)):
                one_course = []
                for j in range(len(tour_list[i])):
                    each = tour_list[i][j]
                    one_course.append(self.__place_list[int(each['id'])]) # 장소 추가
                list.append(one_course) # 코스 추가

            return list
        except Exception as e:
            logger.error(e)
            raise Exception(e)


    def get_recommended_tour_list_based_location(self, user_id, mapX, mapY, radius, **kwargs):
        places = self.__get_location_based_tour_list(mapX, mapY, radius, **kwargs)
        if len(self.__place_list) == 0:
            return []
        self.__additional_comment = self.__get_personal_comment(user_id)
        comment = self.__get_ai_comment(places)
        # 문자열을 리스트로 변환
        list = []
        tour_list = ast.literal_eval(comment)
        for i in range(len(tour_list)):
            one_course = []
            for j in range(len(tour_list[i])):
                each = tour_list[i][j]
                one_course.append(self.__place_list[int(each['id'])])  # 장소 추가
            list.append(one_course)  # 코스 추가

        return list