import anthropic

from .tour_api import *
import ast
from usr.models import User



class AiTourRecommender:
    # SYSTEM_TEXT = '너는 여행사 투어 가이드야. 하루치 일정을 짜려고 해. 반드시 대답은 부가 설명없이 파이썬 딕셔너리를 원소로 갖는 리스트로만 대답해줘야해. 예를들어, [[{\'id\': \'0\', \'name\': \'A\', \'mapX\': \'126\', \'mapY\': \'37\'}, {\'id\': \'1\', \'name\': \'A\', \'mapX\': \'126\', \'mapY\': \'37\'}], [{\'id\': \'7\', \'name\': \'A\', \'mapX\': \'126\', \'mapY\': \'37\'}]] 이렇게. 예시 데이터를 보면 알겠지만 여행 계획 하나당 하나의 리스트로 구성해서, 전체는 리스트 형태로 묶어서 출력해줘. 또한, 정보를 줄때 혹시나 이스케이프 코드가 있다면 모두 제거한 후 정보를 주고, json 문법에 맞게 출력해야해.'
    # SYSTEM_TEXT = "너는 여행사 투어 가이드야. 하루치 여행 일정을 짜야 해.\n출력은 오직 아래 예시와 동일한 형식의 JSON 데이터만 포함해야 하며, 추가 설명이나 이스케이프 코드는 절대 포함하면 안돼.\n각 여행 일정은 하나의 리스트로 구성되고, 전체 결과는 이러한 일정 리스트들을 포함하는 리스트여야 해.\n각 장소는 Python 딕셔너리 형식으로 표현하며, 반드시 다음 키들만 사용해: \"id\", \"name\", \"mapX\", \"mapY\".\n모든 중괄호와 대괄호는 반드시 올바르게 닫혀 있어야 하며, 유효한 JSON 문법을 따라야 해.\n출력 예시:\n[\n  [\n    {\"id\": \"0\", \"name\": \"A\", \"mapX\": \"126\", \"mapY\": \"37\"},\n    {\"id\": \"1\", \"name\": \"B\", \"mapX\": \"127\", \"mapY\": \"38\"}\n  ],\n  [\n    {\"id\": \"2\", \"name\": \"C\", \"mapX\": \"128\", \"mapY\": \"39\"}\n  ]\n]"
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
    # CONTENT_TEXT = """
    # \n이 리스트를 보고 대한민국에서 가장 유명한 장소들만 골라서 여행 경로를 구성해줘. 여행 경로는 최소 4가지 였으면 좋겠어.
    # """
    CONTENT_TEXT = """
    \n이 리스트에는 각각 관광, 레포츠, 문화, 쇼핑 시설 정보가 들어있는 리스트가 있어. 각 시설 리스트에서 대한민국에서 유명한 시설들만 적절히 골라서 여행 코스를 구성해줘.
    대한민국에서 유명한 장소들만 골라서 하루치 여행 코스를 기획했다면, 각 장소들이 위도, 경도를 기준으로 이동하기 가장 적합하도록 장소 순서를 다시 재배치해줘.
    각 여행코스 리스트 안의 index 순서가 여행 순서야.
    여행 코스는 최소 4가지 경우 이상으로 구성했으면 좋겠고, 한 여행 코스에는 같은 장소가 반복되면 안돼.
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
        if sigunguCode is not None:
            data['sigunguCode'] = sigunguCode
        self.__place_list += tour.get_area_based_list(**data) # result 요소에는 Area 객체가 들어옵니다.
        print(self.__place_list)
        list = []
        for i in range(len(self.__place_list)):
            each = self.__place_list[i]
            list.append({
                'id': i,
                'name': each.get_title(),
                'mapX': each.get_mapX(),
                'mapY': each.get_mapY(),
            })

        return [list] # 정보 구분 위해 리스트로 감쌉니다.

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
        system = self.SYSTEM_TEXT
        content = str(place_list) + self.CONTENT_TEXT + self.__additional_comment
        print(self.__additional_comment)
        client = anthropic.Anthropic(api_key=self.__ai_service_key)
        message = client.messages.create(
            model='claude-3-7-sonnet-20250219',
            max_tokens=20000,
            system=system,
            messages=[
                {
                    "role": 'user',
                    "content": [
                        {
                            'type': 'text',
                            'text': content,
                        }
                    ]
                }
            ]
        )
        print(message.content[0].text)
        return message.content[0].text

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
            사용자의 나이대와 성별 정보는 다음과 같아. 다음 정보를 보고 나이대와 성별에 맞게 장소 추천을 해줬으면 좋겠어.
            참고로 나이대는 예를들어서 1세이상 9세 이하면 1~9로 표기돼.\n
            나이대: {user.age_range}, 성별: {user.gender}
            """




    def get_recommended_tour_list_based_area(self, user_id, areaCode=AreaCode.SEOUL, arrange=Arrange.TITLE_IMAGE, sigunguCode=None):
        """

        :return: 파이썬 리스트를 반환합니다.
        """
        places = []
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.GWANGWANGJI, arrange, sigunguCode)) # 관광지 정보 추가
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.LEIPORTS, arrange, sigunguCode)) # 레포츠 정보 추가
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.MUNHWASISUL, arrange, sigunguCode)) # 문화 시설
        places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.SHOPPING, arrange, sigunguCode)) # 쇼핑 정보
        # places.append(self.__get_area_based_tour_list(areaCode, ContentTypeId.SUKBAK, arrange, sigunguCode))  # 숙박 정보
        self.__additional_comment = self.__get_personal_comment(user_id)
        comment = self.__get_ai_comment(places)
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