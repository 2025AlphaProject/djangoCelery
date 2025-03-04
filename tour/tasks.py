from celery import shared_task  # shared_task는 장고와 연관이 있는 작업일 때 사용하는 어노테이션 입니다.
from modules.ai_recommender import AiTourRecommender
from modules.tour_api import Arrange
from config.settings import AI_SERVICE_KEY, PUBLIC_DATA_PORTAL_API_KEY
from celery.signals import task_success, task_failure
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_group_name = None # channel 그룹 이름입니다.

@shared_task
def get_recommended_tour_based_area(group_name, area_code, content_type_id, arrange=Arrange.TITLE_IMAGE, sigungu_code=None):
    recommender = AiTourRecommender(ai_service_key=AI_SERVICE_KEY,
                                    tour_service_key=PUBLIC_DATA_PORTAL_API_KEY) # ai 투어 추천자 생성
    global channel_group_name
    channel_group_name = group_name
    data = {
        'area_code': area_code,
        'content_type_id': content_type_id,
        'arrange': arrange,
    }
    if sigungu_code is not None:
        data['sigungu_code'] = sigungu_code
    recommended_list = recommender.get_recommended_tour_list_based_area(**data)
    return recommended_list

@task_success.connect
def task_success_handler(sender, result, **kwargs):
    """
        Celery 작업이 성공적으로 완료되었을 때 호출됨.
        """
    task_id = sender.request.id # 작업 아이디를 가져옵니다.

    # A 컨테이너의 Django Channels를 통해 클라이언트에게 WebSocket 메시지 전송
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"{channel_group_name}",
        {
            "type": "task_update",
            "message": {
                "task_id": task_id,
                "status": "SUCCESS",
                "result": result,
            },
        },
    )

@task_failure.connect
def task_failure_handler(sender, exception, **kwargs):
    """
    Celery 작업이 실패했을 때 호출됨.
    """
    task_id = sender.request.id

    # A 컨테이너의 Django Channels를 통해 클라이언트에게 WebSocket 메시지 전송
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"{channel_group_name}",
        {
            "type": "task_update",
            "message": {
                "task_id": task_id,
                "status": "FAILURE",
                "result": str(exception),
            },
        },
    )
