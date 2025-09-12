from rest_framework import status
from rest_framework.response import Response

from utils.constants import ResponseCode, ResponseMessage


class APISuccessResponse(Response):
    def __init__(
        self,
        *,
        code: int = ResponseCode.SUCCESS,
        data: dict = None,
        msg: str = ResponseMessage.SUCCESS,
        status_code: int = status.HTTP_200_OK,
        **kwargs,
    ):
        payload = {'code': code, 'msg': msg, 'data': data if data is not None else {}}

        super().__init__(data=payload, status=status_code)


class APIFailedResponse(Response):
    def __init__(
        self,
        *,
        code: int,
        msg: str,
        details: dict = None,
        status_code: int = status.HTTP_200_OK,
        **kwargs,
    ):
        payload = {'code': code, 'msg': msg, 'details': details}
        super().__init__(data=payload, status=status_code)
