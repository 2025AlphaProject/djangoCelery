from celery import shared_task  # shared_task는 장고와 연관이 있는 작업일 때 사용하는 어노테이션 입니다.

from .modules.ai_recommender import AiTourRecommender
from .modules.tour_api import Arrange
from config.settings import AI_SERVICE_KEY, PUBLIC_DATA_PORTAL_API_KEY
from celery.signals import task_success, task_failure
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import requests
from config.settings import APP_LOGGER
from .models import Event, Place, RelationPlace
import datetime
import logging
from services.tour_api_service import TourAPIService
from .services import RelationTourSaveService
logger = logging.getLogger(APP_LOGGER)

channel_group_name = None # channel 그룹 이름입니다.

@shared_task
def get_recommended_place_by_category_task(user_id, areaCode, categoryNames, sigunguCode=None,
                                           arrange=Arrange.TITLE_IMAGE, group_name=None):  # <- group_name 추가
    global channel_group_name # 전역 변수 사용 선언
    if group_name:
        channel_group_name = group_name

    """
    사용자 요청 기반, 특정 카테고리에 대해 AI가 추천한 장소 최대 5개 반환
    """
    logger.info(f'카테고리 추천 요청: user_id={user_id}, areaCode={areaCode}, categoryName={categoryNames}')
    recommender = AiTourRecommender(ai_service_key=AI_SERVICE_KEY,
                                    tour_service_key=PUBLIC_DATA_PORTAL_API_KEY)

    result_places = recommender.get_recommended_places_by_categories(
        user_id=user_id,
        areaCode=areaCode,
        category_names=categoryNames,
        sigunguCode=sigunguCode,
        arrange=arrange
    )

    # 실제 필요한 정보만 추려서 리스트로 반환
    result = {}
    for category, places in result_places.items():
        result[category] = [{
            'address': place.road_address,
            'areaCode': place.areacode,
            'contentId': place.contentid,
            'mapX': place.mapX,
            'mapY': place.mapY,
            'title': place.name,
            'image1': place.place_image,
        } for place in places]

    logger.info(f'total_reuslt:{result}')
    return result


@task_success.connect
def task_success_handler(sender, result, **kwargs):
    """
        Celery 작업이 성공적으로 완료되었을 때 호출됨.
    """

    logger.info(f'task success: {sender.request.id}')
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

    logger.info(f'task failure: {sender.request.id}, error Message: {exception}')
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
    logger.info('storing near events....')

    DATA_BASE_URL = 'http://apis.data.go.kr/B551011/KorService2'
    service_name = 'searchFestival2'
    url = f'{DATA_BASE_URL}/{service_name}'
    response_type = 'json'
    how_many = 50
    today = datetime.date.today()

    params = {
        'serviceKey': PUBLIC_DATA_PORTAL_API_KEY,
        'MobileOS': 'AND',
        'MobileApp': 'Alpha',
        '_type': response_type,
        'eventStartDate': today.strftime('%Y%m%d'),
        'pageNo': 1,
        'numOfRows': 1,
    }

    response = requests.get(url, params=params)
    list_total_count = response.json()['response']['body']['totalCount']

    for page in range(1, (list_total_count // how_many) + 2):
        params['pageNo'] = page
        params['numOfRows'] = how_many
        response = requests.get(url, params=params)

        data_list = response.json()['response']['body']['items']['item']
        if isinstance(data_list, dict):
            data_list = [data_list]

        for each in data_list:
            start = datetime.datetime.strptime(each['eventstartdate'], '%Y%m%d').date()
            end = datetime.datetime.strptime(each['eventenddate'], '%Y%m%d').date()

            Event.objects.get_or_create(
                title=each['title'],
                defaults={
                    'category': each.get('cat1', ''),
                    'title': each['title'],
                    'img_url': each.get('firstimage', '') or each.get('firstimage2', ''),
                    'start_date': start.strftime('%Y-%m-%d'),
                    'end_date': end.strftime('%Y-%m-%d'),
                    'mapX': float(each.get('mapx')),
                    'mapY': float(each.get('mapy')),
                    'homepage_url': each.get('homepage', '')
                }
            )


@shared_task
def save_new_places():
    # logger.info('removing old places....')
    # Place.objects.all().delete()
    logger.info('saving places....')
    tour_api_service = TourAPIService(service_key=PUBLIC_DATA_PORTAL_API_KEY)
    numOfRows = 1500 # 한번에 1000개의 장소만 가져옵니다.
    pageNo = 1
    while True:
        logger.info(f'pageNo: {pageNo} 장소 저장 시도 중입니다....')
        places = tour_api_service.get_area_based_list(
            numOfRows=numOfRows,
            pageNo=pageNo,
        )

        if pageNo >= tour_api_service.total_count // numOfRows + 1:
            break

        for place in places:
            obj, created = Place.objects.update_or_create(
                contentid=place.contentid,
                defaults={
                    "mapX": place.mapx,
                    "mapY": place.mapy,
                    "name": place.title,
                    "cat1": place.cat1,
                    "cat2": place.cat2,
                    "cat3": place.cat3,
                    "place_image": place.firstimage,
                    "areacode": place.areacode,
                    "sigungucode": place.sigungucode,
                    "contenttypeid": place.contenttypeid,
                    "zipcode": place.zipcode,
                    "lDongRegnCd": place.lDongRegnCd,
                    "lDongSignguCd": place.lDongSignguCd,
                    "lclsSystm1": place.lclsSystm1,
                    "lclsSystm2": place.lclsSystm2,
                    "lclsSystm3": place.lclsSystm3,
                    "tel": place.tel,
                    "road_address": place.addr1
                }
            )
        pageNo += 1
    logger.info(f'All places saved')

@shared_task
def save_rel_places():
    """
        연관 관광지 정보 저장 task
    """
    # 모든 연관 관광지 정보를 저장합니다.
    service = RelationTourSaveService()
    service.save_all_rel_places()
    # 로깅을 통해 관광지 정보 성공여부를 보여줍니다.
    logger.info('saving related places SUCCESS')

@shared_task
def delete_all_related_places():
    """
        장소 정보 삭제 위한 임시 함수
    """
    RelationPlace.objects.all().delete()
    logger.info('deleted all related places')
