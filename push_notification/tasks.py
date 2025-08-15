from calendar import month

from celery import shared_task
from django.db.models import QuerySet
from firebase_admin import messaging, auth
from usr.models import User, FCMToken
from django.conf import settings
import logging
from tour.models import Travel
from django.utils import timezone
from datetime import timedelta
from typing import List, Optional
from dateutil.relativedelta import relativedelta

APP_LOGGER = getattr(settings, 'APP_LOGGER')
logger = logging.getLogger(APP_LOGGER)


def get_user_fcm_tokens(user_id: int) -> Optional[QuerySet]:
    """사용자의 FCM 토큰들을 조회합니다."""
    try:
        client = User.objects.get(sub=user_id)
        client_fcm_tokens = FCMToken.objects.filter(user=client)
        logger.info(f'tokens: {client_fcm_tokens}')

        if len(client_fcm_tokens) == 0:
            raise Exception('No FCMToken')

        return client_fcm_tokens
    except User.DoesNotExist:
        logger.error(f'User Not Found. user_id: {user_id}')
        return None
    except Exception as e:
        logger.error(f'Exception: {e}')
        return None


def get_android_config() -> messaging.AndroidConfig:
    """Android 푸시 알림 설정을 반환합니다."""
    return messaging.AndroidConfig(
        priority='high',
        notification=messaging.AndroidNotification(
            channel_id='high_importance_channel',  # 앱에서 생성한 채널 ID와 동일해야 함
            sound='default',  # 사운드 켜야 배너 잘 뜸
        )
    )


def send_notification_to_tokens(fcm_tokens: QuerySet[FCMToken], title: str, body: str,
                                deeplink: str, user_id: int) -> None:
    """FCM 토큰들에게 알림을 전송합니다."""
    android_config = get_android_config()

    for fcm_token in fcm_tokens:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=fcm_token.fcm_token,
            data={
                'user': str(user_id),
                'deeplink': deeplink,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
            },
            android=android_config,
        )

        try:
            response = messaging.send(message)
            logger.info(f'user: {user_id}. Message sent')
        except Exception as e:
            logger.error(f'Failed to send message to user {user_id}: {e}')


def send_tour_notifications(tours, notification_config: dict) -> None:
    """투어 사용자들에게 알림을 전송하는 공통 함수"""
    for tour in tours:
        users = tour.user.all()
        for user in users:
            user_id = user.sub
            fcm_tokens = get_user_fcm_tokens(user_id)

            if fcm_tokens is None:
                continue

            # 알림 메시지 포맷팅
            title = notification_config['title']
            body = notification_config['body'].format(tour_name=tour.tour_name)
            deeplink = f"conever://snapshot?id={tour.id}"

            send_notification_to_tokens(fcm_tokens, title, body, deeplink, user_id)


@shared_task
def send_push_notifications_about_end_tour():
    """
    오후 10시에 여행 종료 알림을 보내줍니다.
    """
    tours = Travel.objects.filter(tour_date=timezone.localdate())

    notification_config = {
        'title': '오늘 여행은 잘 마무리 되셨나요?',
        'body': '오늘 찍은 사진들로 나만의 인생네컷을 만들어보세요! 추억이 더욱 특별해집니다! \'{tour_name}\'에서 찍었던 사진을 업로드 해보세요!'
    }

    send_tour_notifications(tours, notification_config)


@shared_task
def send_push_noti_deadline():
    """
    인생네컷 업로드 마감 시한을 알리는 알림을 보냅니다.
    저녁 6시에 알림을 보냅니다.
    """
    DURATION_DAYS = 3  # 업로드 허용 기간
    tours = Travel.objects.filter(tour_date=timezone.localdate() - timedelta(days=DURATION_DAYS))

    notification_config = {
        'title': '추억을 인생네컷으로 남겨요! 🌟',
        'body': '📸 오늘까지! \'{tour_name}\'에서 찍은 사진을 올리면 인생네컷으로 만들어드려요!'
    }

    send_tour_notifications(tours, notification_config)

@shared_task
def send_push_noti_memory():
    """
        추억 관련 알림을 보냅니다.
        3개월, 6개월, 1년, 2년, 5년 단위로 추억을 보냅니다.
        오후 2시에 알림을 보냅니다.
    """
    DURATION_MONTHS = [3, 6, 12, 24, 60]
    for duration in DURATION_MONTHS:
        tours = Travel.objects.filter(tour_date=timezone.localdate() - relativedelta(months=duration))
        duration_title = f'{duration}개월 전' if duration < 12 else f'{duration // 12}년 전'
        notification_config = {
            'title': f'{duration_title}의 추억을 다시 만나보세요! 📸',
            'body': duration_title + ', \'{tour_name}\' 여행을 기억하시나요? 그때의 사진과 인생네컷을 지금 감상해보세요!'
        }
        send_tour_notifications(tours, notification_config)
