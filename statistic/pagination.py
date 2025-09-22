from collections import defaultdict
from typing import List, OrderedDict

from django.core.paginator import InvalidPage, Paginator
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class MemberRouteListPagination(PageNumberPagination):
    """
    專門用於member聚合數據的分頁器
    先對member進行分頁，再聚合每個member的相關數據
    """

    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'offset'
    max_page_size = 100

    def get_page_number(self, request, paginator):
        """
        從offset參數計算頁碼
        offset=0 -> page=1, offset=10 -> page=2 (當page_size=10時)
        """
        offset = request.query_params.get(self.page_query_param, 0)
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0

        page_number = (offset // self.get_page_size(request)) + 1
        return page_number

    def paginate_queryset(self, queryset, request, view=None):
        """
        對queryset進行member聚合分頁
        """
        # 獲取分頁大小
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        # 先獲取所有有數據的member_ids（去重並排序）
        member_ids = (
            queryset.values_list('ride_session__bike_rental__member_id', flat=True)
            .distinct()
            .order_by('ride_session__bike_rental__member_id')
        )

        # 對member_ids分頁
        paginator = Paginator(list(member_ids), page_size)
        page_number = self.get_page_number(request, paginator)

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg)

        # 獲取當前頁的member_ids
        paginated_member_ids = self.page.object_list

        # 根據分頁後的member_ids查詢對應的數據
        filtered_queryset = queryset.filter(
            ride_session__bike_rental__member_id__in=paginated_member_ids
        )

        # 按member聚合數據
        member_routes = defaultdict(list)
        for route_match in filtered_queryset:
            member = route_match.ride_session.bike_rental.member
            member_routes[member.id].append(route_match)

        # 構建結果，保持member_id的順序
        result_data = []
        for member_id in paginated_member_ids:
            if member_id in member_routes:
                routes = member_routes[member_id]
                member = routes[0].ride_session.bike_rental.member
                result_data.append({'member': member, 'routes': routes})

        # 如果沒有數據，返回None讓DRF處理
        if len(result_data) == 0:
            return None

        return result_data

    def get_paginated_response(self, data):
        """
        返回標準的DRF分頁響應格式
        """
        return Response(
            OrderedDict(
                [
                    ('count', self.page.paginator.count),
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                ]
            )
        )

    def get_next_link(self):
        """
        生成下一頁的連結（使用offset參數）
        """
        if not self.page.has_next():
            return None

        page_number = self.page.next_page_number()
        offset = (page_number - 1) * self.get_page_size(self.request)
        return self.replace_query_param(
            self.request.build_absolute_uri(), self.page_query_param, offset
        )

    def get_previous_link(self):
        """
        生成上一頁的連結（使用offset參數）
        """
        if not self.page.has_previous():
            return None

        page_number = self.page.previous_page_number()
        offset = (page_number - 1) * self.get_page_size(self.request)
        return self.replace_query_param(
            self.request.build_absolute_uri(), self.page_query_param, offset
        )

    def replace_query_param(self, url, key, val):
        """
        替換URL中的查詢參數
        """
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query, keep_blank_values=True)
        query_dict[key] = [str(val)]
        new_query = urlencode(query_dict, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
