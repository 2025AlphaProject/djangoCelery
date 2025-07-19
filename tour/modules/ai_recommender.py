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
                    # sigunguCode가 있는 경우, 각 sigunguCode에 대해 반복해야 하지만,
                    # 현재 로직에서는 복잡해지므로 일단 sigunguCode가 없을 때의 페이징에 집중합니다.
                    # 이 부분은 추후 개선이 필요할 수 있습니다.
                    places = tour.get_area_based_list(**data)
                    if not places: # 더 이상 가져올 데이터가 없으면 중단
                        break
                    self.__place_list.extend(places)
                else:
                    places = tour.get_area_based_list(**data)
                    if not places: # 더 이상 가져올 데이터가 없으면 중단
                        break
                    self.__place_list.extend(places)
                
                page_no += 1
                # API 과부하를 막기 위해 간단한 sleep 추가 (선택 사항)
                # import time
                # time.sleep(0.1)

        for i, place in enumerate(self.__place_list):
            raw_data_list.append({
                'id': i,
                'name': place.get_title(),
                'mapX': place.get_mapX(),
                'mapY': place.get_mapY(),
                'contentTypeId': place.get_contentTypeId()
            })

        return raw_data_list

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
           너는 여행사 투어 가이드야. 내가 주는 다양한 카테고리의 장소 리스트 중에서
           요청한 카테고리별로 가장 추천할만한 장소들을 최대 5개씩만 골라줘.
           아래와 같은 JSON 형식으로 출력해줘. 장소 설명이나 부가 설명 없이 반드시 JSON으로만 응답해야 해.
           JSON의 key는 반드시 contentTypeId 숫자로 해야 해.

           {
               "39": [
                   {"id": "0", "name": "맛집A", "mapX": "126.98", "mapY": "37.56"},
                   {"id": "4", "name": "맛집B", "mapX": "126.93", "mapY": "37.57"}
               ],
               "38": [...],
               ...
           }

           contentTypeId는 다음과 같이 대응돼:
           12: 관광지, 14: 문화시설, 15: 축제공연행사,
           28: 레포츠, 32: 숙박, 38: 쇼핑, 39: 음식점
           """
        user_prompt = f"{str(place_list)}\n위 장소들을 다음 카테고리별로 정리해서 최대 5개씩만 골라줘: {category_names}"
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
            place_list = self.__get_all_category_place_list(areaCode, sigunguCode, arrange)

            # AI 호출
            ai_response_text = self.__get_ai_category_comment(place_list, category_names)
            ai_response = json.loads(ai_response_text)

            # 카테고리별 결과 추출
            result = {}
            for category in category_names:
                category_result = ai_response.get(category, [])[:5]
                place_objs = []
                for item in category_result:
                    idx = int(item['id'])
                    if 0 <= idx < len(self.__place_list):
                        place_objs.append(self.__place_list[idx])
                result[category] = place_objs

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
