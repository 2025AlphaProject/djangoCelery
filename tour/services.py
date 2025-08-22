from .relation_place_areacodes import sigungu_codes, get_area_code, convert_rel_api_ac_to_tour_api_ac
from services.tour_api_http_client import RelationPlaceApiHttpClient
from services.tour_api_service import TourAPIService
from django.utils import timezone
from .models import Place, RelationPlace
from datetime import date
from dateutil.relativedelta import relativedelta
from config.settings import APP_LOGGER, PUBLIC_DATA_PORTAL_API_KEY
import logging
from django.db.models import F

logger = logging.getLogger(APP_LOGGER)


class RelationTourSaveService:

    def __init__(self):
        self.http_client = RelationPlaceApiHttpClient()
        self.tour_api = TourAPIService(service_key=PUBLIC_DATA_PORTAL_API_KEY)
        self.numOfRows = 1500 # 한 페이지 결과 수
        self.cached_place_info = None
        self.data_mapping_for_place = {
            'place_name': 'tAtsNm',
            'place_area_cd': 'areaCd',
            'place_area_name': 'areaNm',
            'place_sigungu_cd': 'signguCd',
            'place_sigungu_name': 'signguNm',
        }
        self.data_mapping_for_related_place = {
            'related_place_name': 'rlteTatsNm',
            'related_place_area_cd': 'rlteRegnCd',
            'related_place_area_name': 'rlteRegnNm',
            'related_place_sigungu_cd': 'rlteSignguCd',
            'related_place_sigungu_name': 'rlteSignguNm',
            'related_place_cat1_name': 'rlteCtgryLclsNm',
            'related_place_cat2_name': 'rlteCtgryMclsNm',
            'related_place_cat3_name': 'rlteCtgrySclsNm',
            'rank': 'rlteRank'
        }

    def save_all_rel_places(self):
        """
            모든 연관 장소 정보들을 저장합니다.
        """
        # 모든 지역들에 대해
        for area in sigungu_codes:
            logger.info(f'{area.get('sigunguNm')} 연관 정보 저장중....')
            self.__save_relation_places_by_area(area.get('sigunguCd'))

    def __save_relation_places_by_area(self, sigungu_code):
        # 2024년 5월부터 데이터 존재
        today = timezone.localdate(timezone.now()).today()
        specific_date = today - relativedelta(months=2)
        end_date =  today - relativedelta(months=1)
        while specific_date < end_date:
            logger.info(f'{specific_date.strftime('%Y%m')} 정보 저장 중....')
            self.__save_relation_placdes_by_area_in_date(sigungu_code, specific_date)
            specific_date = specific_date + relativedelta(months=1)


    def __save_relation_placdes_by_area_in_date(self, sigungu_code, specific_date:date):
        page_no = 1
        while True:
            response = self.http_client.get_relation_places_info_based_area(
                pageNo=page_no,
                numOfRows=self.numOfRows,
                baseYm=specific_date.strftime('%Y%m'),
                areaCd=get_area_code(sigungu_code),
                sigunguCd=sigungu_code
            )
            body = response.get('response').get('body')
            total_count = body.get('totalCount')
            if total_count == 0: continue
            # logger.info(body)
            items = body.get('items').get('item')

            for each in items:
                self.__connect_related_place(each)

            if total_count // self.numOfRows < page_no:
                break
            page_no += 1

    def __get_place_by_info(self, name, areaCd, signguNm):
        tour_api_area_cd = convert_rel_api_ac_to_tour_api_ac(areaCd)
        # tour_api_sigungu_cd = self.tour_api.get_sigungu_code_as_name(tour_api_area_cd, signguNm)
        get_data = {
            'name': name,
            'areacode': tour_api_area_cd,
        }
        # if tour_api_sigungu_cd is not None: get_data['sigungucode'] = tour_api_sigungu_cd
        try:
            # mapX, mapY를 필수 파라미터로 안본다면 아래 코드 활성화
            # place = Place.objects.get_or_create(**get_data)
            place = Place.objects.get(**get_data)
            return place
        except (Place.DoesNotExist, Place.MultipleObjectsReturned): # 중복이거나 존재하지 않는 경우 None 반환
            return None

    def __connect_related_place(self, info):
        data = self.__get_data_dict_for_db_save(info)
        rel, created = RelationPlace.objects.get_or_create(
            **data
        )

        # if not created:
        #     # 기존 행이면 원자적으로 +rank
        #     RelationPlace.objects.filter(pk=rel.pk).update(rank=F('rank') + rank)


    def __get_data_dict_for_db_save(self, info):
        data = self.__get_cached_place_data_or_new_data(info).copy()
        for key, value in self.data_mapping_for_related_place.items():
            if key == 'rank':
                data[key] = int(info.get(value))
                continue
            data[key] = info.get(value)

        # data['place'] = self.__get_place_by_info(
        #     info.get('tAtsNm'),
        #     info.get('areaCd'),
        #     info.get('signguNm')
        # )

        data['related_place'] = self.__get_place_by_info(
            info.get('rlteTatsNm'),
            info.get('rlteRegnCd'),
            info.get('rlteSignguNm')
        )

        return data

    def __get_cached_place_data_or_new_data(self, info):
        if self.cached_place_info is None or self.cached_place_info.get('place_name') != info.get('tAtsNm'):
            self.cached_place_info = dict()
            for key, value in self.data_mapping_for_place.items():
                self.cached_place_info[key] = info.get(value)
            self.cached_place_info['place'] = self.__get_place_by_info(
            info.get('tAtsNm'),
            info.get('areaCd'),
            info.get('signguNm')
        )
        return self.cached_place_info