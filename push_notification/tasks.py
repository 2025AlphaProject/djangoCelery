from celery import shared_task
from firebase_admin import messaging, auth
from usr.models import User, FCMToken
from django.conf import settings
import logging
from tour.models import Travel
from django.utils import timezone
from datetime import timedelta

APP_LOGGER = getattr(settings, 'APP_LOGGER')
logger = logging.getLogger(APP_LOGGER)

@shared_task
def send_push_notifications_about_end_tour():
    """
        오후 10시에 여행 종료 알림을 보내줍니다.
    """
    tours = Travel.objects.filter(tour_date=timezone.localdate())
    for tour in tours:
        users = tour.user.all()
        for user in users:
            client_fcm_tokens = None
            user_id = user.sub
            try:
                client = User.objects.get(sub=int(user_id))
                client_fcm_tokens = FCMToken.objects.filter(user=client)
                logger.info(f'tokens: {client_fcm_tokens}')
                if len(client_fcm_tokens) == 0:
                    raise Exception('No FCMToken')
            except User.DoesNotExist:
                logger.error(f'User Not Found. user_id: {user_id}')
            except Exception as e:
                logger.error(f'Exception: {e}')

            android = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='high_importance_channel',  # 앱에서 생성한 채널 ID와 동일해야 함
                    sound='default',  # 사운드 켜야 배너 잘 뜸
                )
            )
            for client_fcm_token in client_fcm_tokens:

                message = messaging.Message(
                    notification=messaging.Notification(
                        title='오늘 여행은 잘 마무리 되셨나요?',
                        body=f'오늘 찍은 사진들로 나만의 인생네컷을 만들어보세요! 추억이 더욱 특별해집니다! \'{tour.tour_name}\'에서 찍었던 사진을 업로드 해보세요!',
                    ),
                    token=client_fcm_token.fcm_token,
                    data={
                        'user': str(user.sub),
                        'deeplink': f'conever://snapshot?id={tour.id}', # scheme://host/path
                        'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                        # 'snapshot_id': '257'
                    },
                    android=android,
                )


                try:
                    response = messaging.send(message)
                    logger.info(f'user: {user_id}. Message sent')
                except Exception as e:
                    logger.error(e)


@shared_task
def send_push_noti_deadline():
    """
        인생네컷 업로드 마감 시한을 알리는 알림을 보냅니다.
        저녁 6시에 알림을 보냅니다.
    """
    DURATION_DAYS = 3 # 업로드 허용 기간
    tours = Travel.objects.filter(tour_date=timezone.localdate() - timedelta(days=DURATION_DAYS))
    for tour in tours:
        users = tour.user.all()
        for user in users:
            client_fcm_tokens = None
            user_id = user.sub
            try:
                client = User.objects.get(sub=int(user_id))
                client_fcm_tokens = FCMToken.objects.filter(user=client)
                logger.info(f'tokens: {client_fcm_tokens}')
                if len(client_fcm_tokens) == 0:
                    raise Exception('No FCMToken')
            except User.DoesNotExist:
                logger.error(f'User Not Found. user_id: {user_id}')
            except Exception as e:
                logger.error(f'Exception: {e}')

            android = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='high_importance_channel',  # 앱에서 생성한 채널 ID와 동일해야 함
                    sound='default',  # 사운드 켜야 배너 잘 뜸
                )
            )
            for client_fcm_token in client_fcm_tokens:

                message = messaging.Message(
                    notification=messaging.Notification(
                        title='추억을 인생네컷으로 남겨요! 🌟',
                        body=f'📸 오늘까지! \'{tour.tour_name}\'에서 찍은 사진을 올리면 인생네컷으로 만들어드려요!',
                    ),
                    token=client_fcm_token.fcm_token,
                    data={
                        'user': str(user.sub),
                        'deeplink': f'conever://snapshot?id={tour.id}',  # scheme://host/path
                        'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                        # 'snapshot_id': '257'
                    },
                    android=android,
                )

                try:
                    response = messaging.send(message)
                    logger.info(f'user: {user_id}. Message sent')
                except Exception as e:
                    logger.error(e)
