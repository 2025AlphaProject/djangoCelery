from celery import shared_task  # shared_task는 장고와 연관이 있는 작업일 때 사용하는 어노테이션 입니다.
from django.template.defaultfilters import title

from .modules.ai_recommender import AiTourRecommender
from .modules.tour_api import Arrange
from config.settings import AI_SERVICE_KEY, PUBLIC_DATA_PORTAL_API_KEY
from celery.signals import task_success, task_failure
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import requests
from config.settings import SEOUL_PUBLIC_DATA_SERVICE_KEY
from .models import Event
import datetime

channel_group_name = None # channel 그룹 이름입니다.

@shared_task
def get_recommended_tour_based_area(group_name, area_code, content_type_id, arrange=Arrange.TITLE_IMAGE, sigungu_code=None):
    recommender = AiTourRecommender(ai_service_key=AI_SERVICE_KEY,
                                    tour_service_key=PUBLIC_DATA_PORTAL_API_KEY) # ai 투어 추천자 생성
    global channel_group_name
    channel_group_name = group_name
    data = {
        'areaCode': area_code,
        'contentTypeId': content_type_id,
        'arrange': arrange,
    }
    if sigungu_code is not None:
        data['sigunguCode'] = sigungu_code
    recommended_list = recommender.get_recommended_tour_list_based_area(**data)
    for i in range(len(recommended_list)):
        course = recommended_list[i]
        for j in range(len(course)):
            place = course[j]
            data = {
                'address': place.get_address(),
                'areaCode': place.get_area_code(),
                'contentId': place.get_contentId(),
                'mapX': place.get_mapX(),
                'mapY': place.get_mapY(),
                'title': place.get_title(),
                'image1': place.get_image1_url(),
                'image2': place.get_image2_url(),
            }
            course[j] = data
    return recommended_list

@task_success.connect
def task_success_handler(sender, result, **kwargs):
    """
        Celery 작업이 성공적으로 완료되었을 때 호출됨.
    """
    if sender.name == 'app.tasks.get_recommended_tour_based_area':
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
    if sender.name == 'app.tasks.get_recommended_tour_based_area':
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

@shared_task
def remove_old_events():
    """
    오래된 이벤트 정보는 삭제를 진행합니다.
    """
    today = datetime.date.today()
    Event.objects.filter(end_date__lt=today).delete() # 이벤트 마지막 날짜보다 작을 경우 데이터 삭제 진행

@shared_task
def store_near_events():
    # API 연결
    SEOUL_DATA_BASE_URL = 'http://openapi.seoul.go.kr:8088'
    response_type = 'json'
    service_name = 'culturalEventInfo'
    start_index = 1
    url = SEOUL_DATA_BASE_URL + f'/{SEOUL_PUBLIC_DATA_SERVICE_KEY}/{response_type}/{service_name}'
    # list_total_count 정보를 위해 정보 하나만 가져옵니다.
    response = requests.get(url + '/1/1/')
    list_total_count = response.json()['culturalEventInfo']['list_total_count'] # 총 리스트 갯수를 나타냅니다.
    # api로부터 정보 50개씩 가져옵니다.
    how_many = 50 # 정보 갯수
    flag = False # 각 정보가 오늘 날짜보다 과거일 경우 True로 변환하여 for문을 빠져나갑니다.
    today = datetime.date.today() # 오늘 날짜를 가져옵니다.
    for i in range(start_index, list_total_count, how_many):
        response = requests.get(url + f'/{i}/{i + how_many - 1}/')
        # 정보 저장
        data_list = response.json()['culturalEventInfo']['row']
        for each in data_list:
            if datetime.datetime.strptime(each['END_DATE'].split()[0], '%Y-%m-%d') < today: # 이벤트가 과거 정보라면
                # 데이터가 뒤로갈수록 오래된 이벤트 정보이므로 바로 break문 걸어서 종료 시켜도 무방
                flag = True
                break
            # 이벤트를 만듭니다.
            try:
                Event.objects.get(title=each['TITLE'])
            except Event.DoesNotExist: # 이벤트가 등록되지 않았다면
                Event.objects.create(
                    category=each['CODENAME'],
                    gu_name=each['GUNAME'],
                    title=each['TITLE'],
                    img_url=each['MAIN_IMG'],
                    start_date=each['STARTDATE'].split()[0],
                    end_date=each['END_DATE'].split()[0],
                    mapX=float(each['LAT']),
                    mapY=float(each['LOT']),
                )
        if flag: break




    # DB에 데이터 저장