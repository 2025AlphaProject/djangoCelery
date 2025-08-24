import anthropic
import json
from .tour_api import *
import ast
from usr.models import User
from .ai_models.ai_service import get_ai_response
from .ai_models import claude_ai, deepseek_ai, gemini_ai
from config.settings import APP_LOGGER
import logging
logger = logging.getLogger(APP_LOGGER)
from tour.models import Place


class AiTourRecommender:
    AI_MODEL = gemini_ai.GeminiModel()

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

    def __get_all_category_place_list(self, areaCode, sigunguCode=None, arrange=Arrange.TITLE_IMAGE):
        """
        ContentTypeId 전체를 순회하며 해당 지역(place) 리스트를 self.__place_list에 저장하고,
        AI에게 넘길 수 있는 가공된 딕셔너리 리스트로 반환합니다.
        """
        self.__place_list = []  # 기존 데이터 초기화
        tour = TourApi(MobileOS=MobileOS.ANDROID, MobileApp='AiTourRecommender', service_key=self.__tour_service_key)
        raw_data_list = []

        for content_type in ContentTypeId:
            page_no = 1
            while True:
                data = {
                    'areaCode': areaCode.value if isinstance(areaCode, Enum) else areaCode,
                    'contentTypeId': content_type.value,
                    'arrange': arrange.value if isinstance(arrange, Enum) else arrange,
                    'pageNo': page_no,
                    'numOfRows': 100  # 한 페이지에 100개씩
                }

                if sigunguCode:
                    data['sigunguCode'] = sigunguCode
                try:
                    places = tour.get_area_based_list(**data)
                except TypeError:
                    places = []

                if places is None:
                    places = []
                if not isinstance(places, list):
                    places = [places]
                if not places:
                    break
                self.__place_list.extend(places)
                page_no += 1


        for i, place in enumerate(self.__place_list):
            str_id = str(i)
            raw_data_list.append({
                'id': i,
                'name': place.get_title(),
                'mapX': place.get_mapX(),
                'mapY': place.get_mapY(),
                'contentTypeId': place.get_contentTypeId()
            })

        return raw_data_list

    def __get_all_category_place_list_from_db(self, areaCode, sigunguCode=None):
        if isinstance(sigunguCode, list):
            sigunguCode = sigunguCode[0]
        places = Place.objects.filter(areacode=str(areaCode), sigungucode=str(sigunguCode)) if sigunguCode else Place.objects.filter(areacode=str(areaCode))
        logger.info(f'count: {places.count()}')
        logger.info(f'areaCode {areaCode} sigunguCode {sigunguCode}')
        ans = []
        for each in places:
            ans.append({
                'id': each.id,
                'name': each.name,
                'mapX': each.mapX,
                'mapY': each.mapY,
                'contentTypeId': each.contenttypeid
            })
        return ans

    def __get_ai_category_comment(self, place_list, category_names):
        """
        AI에게 모든 장소 리스트를 넘기고, 카테고리별로 추천 장소를 정제해달라고 요청하는 함수입니다.
        AI는 각 contentTypeId에 대해 적절한 장소를 분류하여 JSON 형식으로 반환해야 합니다.
        예시:
        {
            "음식점": [ {"id": "0", "name": "A", "mapX": "126.1", "mapY": "37.5"}, ... ],
            "쇼핑": [...],
            ...
        }
        """
        self.AI_MODEL.ai_service_key = self.__ai_service_key
        system_prompt = """
           당신은 한국 여행 큐레이터입니다.

            [목표]
            - 입력 리스트의 '순서'는 무시하고, 각 항목을 '유명도/대표성' 기준으로 점수화한 뒤,
              요청한 contentTypeId별로 상위 10개를 선정하세요.
            - 같은 체인/유사 카테고리의 중복은 줄이고(다변성), 해운대·송정·센텀 등 지역이 편향되지 않게 하세요.
            
            [입력]
            - items: JSON 배열(각 항목: {id, name, mapX, mapY, contentTypeId})
            - target_types: 예) ["12","14","39"]
            
            [선정 규칙]
            1) 리스트 순서는 절대 사용하지 마세요. 반드시 전 항목을 스캔해 점수화하세요.
            2) 점수 = 유명도(전국적 인지도/상징성) + 방문가치(랜드마크성/체험성) – 중복패널티.
               - 동점이면 tie_breaker = (id를 숫자로 간주하여 97로 나눈 나머지)가 큰 순.
            3) 편향 방지: 최종 10개 중 최소 5개는 입력리스트의 후반 사분위(하위 50%)에서 선발하도록 우선 고려.
            4) 결과는 contentTypeId별로 상위 10개만, 아래 출력 포맷으로 내세요.
            5) 출력은 JSON만. id/mapX/mapY는 문자열로 캐스팅하세요.
            
            [출력 포맷]
            {
              "12": [{"id":"", "name":"", "mapX":"", "mapY":""}, ...최대 10],
              "14": [...],
              "39": [...]
            }
            
            [지금 할 일]
            - items와 target_types를 받으면 위 규칙으로 재순위화 후 JSON만 출력.

           """
        logger.info(str(place_list))
        user_prompt = f"items:{str(place_list)}\ntarget_types:{category_names}"
        return get_ai_response(self.AI_MODEL, system_prompt, user_prompt)

    def get_recommended_places_by_categories(self, user_id, areaCode, category_names: list, sigunguCode=None,
                                             arrange=Arrange.TITLE_IMAGE):
        """
        복수 카테고리를 입력받아 각 카테고리별 최대 5개의 추천 장소 반환.
        category_names: 예) ['음식점', '관광지']
        결과: { '음식점': [Place, ...], '관광지': [Place, ...] }
        """
        try:
            self.__additional_comment = self.__get_personal_comment(user_id)

            # 모든 장소 수집
            # place_list = self.__get_all_category_place_list(areaCode, sigunguCode, arrange)
            place_list = self.__get_all_category_place_list_from_db(areaCode, sigunguCode)


            # AI 호출
            ai_response_text = self.__get_ai_category_comment(place_list, category_names)
            ai_response = json.loads(ai_response_text)
            # ai_response = []

            # 카테고리별 결과 추출
            result = {}
            for category in category_names:
                category_result = ai_response.get(category, [])[:10]
                place_objs = []
                for item in category_result:
                    place_objs.append(Place.objects.get(id=int(item['id'])))
                #     idx = int(item['id'])
                #     # if 0 <= idx < len(self.__place_list):
                #     place_objs.append(self.__place_list[idx])
                result[category] = place_objs

            logger.info(f'result: {result}')
            return result

        except Exception as e:
            logger.error(e)
            raise Exception(e)

    def __get_personal_comment(self, user_id):
        """
        Ai 프롬프팅에 넣을 사용자 맞춤 정보를 설정합니다.
        """
        user = None
        try:
            user = User.objects.get(sub=user_id)
        except User.DoesNotExist:
            return ""
        if user.gender is None or user.gender == '' or user.age_range is None or user.age_range == '':
            logger.info(f'user {user_id} does not have age_range or gender information')
            return ""
        # 유저 정보가 모두 갖춰져 있는 상태라면
        return f"""
                    사용자의 나이대와 성별 정보는 다음과 같아. 다음 정보를 보고 나이대와 성별에 맞게 장소 추천을 해줘.
                    참고로 나이대는 예를들어서 1세이상 9세 이하면 1~9로 표기돼.\n
                    나이대: {user.age_range}, 성별: {user.gender}
                """
