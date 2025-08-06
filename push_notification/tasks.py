from celery import shared_task
from firebase_admin import messaging, auth
from usr.models import User
from django.conf import settings
import logging
from tour.models import Travel
from django.utils import timezone

APP_LOGGER = getattr(settings, 'APP_LOGGER')
logger = logging.getLogger(APP_LOGGER)

@shared_task
def send_push_notifications_about_end_tour():
    """
        오후 10시에 여행 끝 알림을 보내줍니다.
    """
    tours = Travel.objects.filter(tour_date=timezone.localdate())
    for tour in tours:
        users = tour.user.all()
        for user in users:
            client_fcm_token = None
            user_id = user.sub
            try:
                client = User.objects.get(user_id=int(user_id))
                client_fcm_token = client.fcm_token
            except User.DoesNotExist:
                logger.error(f'User Not Found. user_id: {user_id}')

            message = messaging.Message(
                notification=messaging.Notification(
                    title='오늘 여행은 잘 마무리 되셨나요?',
                    body='오늘 찍은 사진들로 나만의 인생네컷을 만들어보세요. 추억이 더욱 특별해집니다!',
                ),
                token=client_fcm_token,
                data={
                    'user': user.sub,
                    'deeplink': 'conever://snapshot/', # scheme://host/path
                    'click_action': 'SNAPSHOT',
                }
            )
            try:
                response = messaging.send(message)
                logger.info(f'user: {user_id}. Message sent')
            except Exception as e:
                logger.error(e)
