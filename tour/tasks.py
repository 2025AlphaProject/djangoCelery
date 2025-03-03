from celery import shared_task  # shared_task는 장고와 연관이 있는 작업일 때 사용하는 어노테이션 입니다.
from modules.ai_recommender import AiTourRecommender
from modules.tour_api import Arrange
from config.settings import AI_SERVICE_KEY, PUBLIC_DATA_PORTAL_API_KEY


@shared_task
def get_recommended_tour_based_area(area_code, content_type_id, arrange=Arrange.TITLE_IMAGE, sigungu_code=None):
    recommender = AiTourRecommender(ai_service_key=AI_SERVICE_KEY,
                                    tour_service_key=PUBLIC_DATA_PORTAL_API_KEY) # ai 투어 추천자 생성
    data = {
        'area_code': area_code,
        'content_type_id': content_type_id,
        'arrange': arrange,
    }
    if sigungu_code is not None:
        data['sigungu_code'] = sigungu_code
    recommended_list = recommender.get_recommended_tour_list_based_area(**data)
    return recommended_list