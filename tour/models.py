from django.db import models

# Create your models here.
class Event(models.Model):
    # id: pk
    category = models.CharField(max_length=100) # 카테고리
    gu_name = models.CharField(max_length=100) # 구 이름을 말합니다.
    title = models.CharField(max_length=300) # 행사 제목
    img_url = models.URLField() # 행사 이미지 url 입니다.
    start_date = models.DateField() # 행사 시작 날짜
    end_date = models.DateField() # 행사 막날 날짜
    mapX = models.FloatField() # 행사 경도 정보
    mapY = models.FloatField() # 행사 위도 정보
    homepage_url = models.URLField() # 홈페이지 URL

    class Meta:
        managed = False # api 컨테이너에서만 테이블을 관리합니다.