from typing import List, Optional, Tuple, Dict, Any, Union
from urllib.parse import urlencode

import httpx
import tenacity
from httpx import ConnectError
from pydantic import ValidationError, BaseModel
from requests.utils import dict_from_cookiejar

from mys_goods_tool.data_model import GameRecord, GameInfo, Good, Address, BaseApiStatus, MmtData, GeetestResult, \
    GetCookieStatus, \
    CreateMobileCaptchaStatus, GetGoodDetailStatus, ExchangeStatus
from mys_goods_tool.user_data import config as conf, UserAccount, BBSCookies, ExchangePlan, ExchangeResult
from mys_goods_tool.utils import generate_device_id, logger, generate_ds, Subscribe, \
    NtpTime, get_async_retry

URL_LOGIN_TICKET_BY_CAPTCHA = "https://webapi.account.mihoyo.com/Api/login_by_mobilecaptcha"
URL_LOGIN_TICKET_BY_PASSWORD = "https://webapi.account.mihoyo.com/Api/login_by_password"
URL_MULTI_TOKEN_BY_LOGIN_TICKET = "https://api-takumi.mihoyo.com/auth/api/getMultiTokenByLoginTicket?login_ticket={0}&token_types=3&uid={1}"
URL_COOKIE_TOKEN_BY_CAPTCHA = "https://api-takumi.mihoyo.com/account/auth/api/webLoginByMobile"
URL_COOKIE_TOKEN_BY_STOKEN = "https://passport-api.mihoyo.com/account/auth/api/getCookieAccountInfoBySToken"
URL_LTOKEN_BY_STOKEN = "https://passport-api.mihoyo.com/account/auth/api/getLTokenBySToken"
URL_STOKEN_V2_BY_V1 = "https://passport-api.mihoyo.com/account/ma-cn-session/app/getTokenBySToken"
URL_ACTION_TICKET = "https://api-takumi.mihoyo.com/auth/api/getActionTicketBySToken?action_type=game_role&stoken={stoken}&uid={bbs_uid}"
URL_GAME_RECORD = "https://api-takumi-record.mihoyo.com/game_record/card/wapi/getGameRecordCard?uid={}"
URL_GAME_LIST = "https://bbs-api.mihoyo.com/apihub/api/getGameList"
URL_MYB = "https://api-takumi.mihoyo.com/common/homutreasure/v1/web/user/point?app_id=1&point_sn=myb"
URL_DEVICE_LOGIN = "https://bbs-api.mihoyo.com/apihub/api/deviceLogin"
URL_DEVICE_SAVE = "https://bbs-api.mihoyo.com/apihub/api/saveDevice"
URL_GOOD_LIST = "https://api-takumi.mihoyo.com/mall/v1/web/goods/list?app_id=1&point_sn=myb&page_size=20&page={" \
                "page}&game={game} "
URL_CHECK_GOOD = "https://api-takumi.mihoyo.com/mall/v1/web/goods/detail?app_id=1&point_sn=myb&goods_id={}"
URL_EXCHANGE = "https://api-takumi.mihoyo.com/mall/v1/web/goods/exchange"
URL_ADDRESS = "https://api-takumi.mihoyo.com/account/address/list?t={}"
URL_REGISTRABLE = "https://webapi.account.mihoyo.com/Api/is_mobile_registrable?mobile={mobile}&t={t}"
URL_CREATE_MMT = "https://webapi.account.mihoyo.com/Api/create_mmt?scene_type=1&now={now}&reason=user.mihoyo.com%2523%252Flogin%252Fcaptcha&action_type=login_by_mobile_captcha&t={t}"
URL_CREATE_MOBILE_CAPTCHA = "https://webapi.account.mihoyo.com/Api/create_mobile_captcha"
URL_GET_USER_INFO = "https://bbs-api.miyoushe.com/user/api/getUserFullInfo?uid={uid}"

HEADERS_WEBAPI = {
    "Host": "webapi.account.mihoyo.com",
    "Connection": "keep-alive",
    "sec-ch-ua": conf.device_config.UA,
    "DNT": "1",
    "x-rpc-device_model": conf.device_config.X_RPC_DEVICE_MODEL_PC,
    "sec-ch-ua-mobile": "?0",
    "User-Agent": conf.device_config.USER_AGENT_PC,
    "x-rpc-device_id": None,
    "Accept": "application/json, text/plain, */*",
    "x-rpc-device_name": conf.device_config.X_RPC_DEVICE_NAME_PC,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "x-rpc-client_type": "4",
    "sec-ch-ua-platform": conf.device_config.UA_PLATFORM,
    "Origin": "https://user.mihoyo.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://user.mihoyo.com/",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
}
HEADERS_PASSPORT_API = {
    "Host": "passport-api.mihoyo.com",
    "Content-Type": "application/json",
    "Accept": "*/*",
    # "x-rpc-device_fp": "",
    "x-rpc-client_type": "1",
    "x-rpc-device_id": None,
    # "x-rpc-app_id": "bll8iq97cem8",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "x-rpc-game_biz": "bbs_cn",
    "Accept-Encoding": "gzip, deflate, br",
    "x-rpc-device_model": conf.device_config.X_RPC_DEVICE_MODEL_MOBILE,
    "User-Agent": conf.device_config.USER_AGENT_OTHER,
    "x-rpc-device_name": conf.device_config.X_RPC_DEVICE_NAME_MOBILE,
    "x-rpc-app_version": conf.device_config.X_RPC_APP_VERSION,
    # 抓包时 "2.47.1"

    "x-rpc-sdk_version": "1.6.1",
    "Connection": "keep-alive",
    "x-rpc-sys_version": conf.device_config.X_RPC_SYS_VERSION
}
HEADERS_API_TAKUMI_PC = {
    "Host": "api-takumi.mihoyo.com",
    "Content-Type": "application/json;charset=utf-8",
    "Origin": "https://bbs.mihoyo.com",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": conf.device_config.USER_AGENT_PC,
    "Referer": "https://bbs.mihoyo.com/",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9"
}
HEADERS_ACTION_TICKET = {
    "Host": "api-takumi.mihoyo.com",
    "x-rpc-device_model": conf.device_config.X_RPC_DEVICE_MODEL_MOBILE,
    "User-Agent": conf.device_config.USER_AGENT_OTHER,
    "Referer": "https://webstatic.mihoyo.com/",
    "x-rpc-device_name": conf.device_config.X_RPC_DEVICE_NAME_MOBILE,
    "Origin": "https://webstatic.mihoyo.com",
    "Content-Length": "66",
    "Connection": "keep-alive",
    "x-rpc-channel": conf.device_config.X_RPC_CHANNEL,
    "x-rpc-app_version": conf.device_config.X_RPC_APP_VERSION,
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "DS": None,
    "x-rpc-device_id": None,
    "x-rpc-client_type": "5",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=utf-8",
    "Accept-Encoding": "gzip, deflate, br",
    "x-rpc-sys_version": conf.device_config.X_RPC_SYS_VERSION,
    "x-rpc-platform": conf.device_config.X_RPC_PLATFORM
}
HEADERS_GAME_RECORD = {
    "Host": "api-takumi-record.mihoyo.com",
    "Origin": "https://webstatic.mihoyo.com",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": conf.device_config.USER_AGENT_MOBILE,
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Referer": "https://webstatic.mihoyo.com/",
    "Accept-Encoding": "gzip, deflate, br"
}
HEADERS_GAME_LIST = {
    "Host": "bbs-api.mihoyo.com",
    "DS": None,
    "Accept": "*/*",
    "x-rpc-device_id": generate_device_id(),
    "x-rpc-client_type": "1",
    "x-rpc-channel": conf.device_config.X_RPC_CHANNEL,
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "x-rpc-sys_version": conf.device_config.X_RPC_SYS_VERSION,
    "Referer": "https://app.mihoyo.com",
    "x-rpc-device_name": conf.device_config.X_RPC_DEVICE_NAME_MOBILE,
    "x-rpc-app_version": conf.device_config.X_RPC_APP_VERSION,
    "User-Agent": conf.device_config.USER_AGENT_OTHER,
    "Connection": "keep-alive",
    "x-rpc-device_model": conf.device_config.X_RPC_DEVICE_MODEL_MOBILE
}
HEADERS_MYB = {
    "Host": "api-takumi.mihoyo.com",
    "Origin": "https://webstatic.mihoyo.com",
    "Connection": "keep-alive",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": conf.device_config.USER_AGENT_MOBILE,
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Referer": "https://webstatic.mihoyo.com/",
    "Accept-Encoding": "gzip, deflate, br"
}
HEADERS_DEVICE = {
    "DS": None,
    "x-rpc-client_type": "2",
    "x-rpc-app_version": conf.device_config.X_RPC_APP_VERSION,
    "x-rpc-sys_version": conf.device_config.X_RPC_SYS_VERSION_ANDROID,
    "x-rpc-channel": conf.device_config.X_RPC_CHANNEL_ANDROID,
    "x-rpc-device_id": None,
    "x-rpc-device_name": conf.device_config.X_RPC_DEVICE_NAME_ANDROID,
    "x-rpc-device_model": conf.device_config.X_RPC_DEVICE_MODEL_ANDROID,
    "Referer": "https://app.mihoyo.com",
    "Content-Type": "application/json; charset=UTF-8",
    "Host": "bbs-api.mihoyo.com",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "User-Agent": conf.device_config.USER_AGENT_ANDROID_OTHER
}
HEADERS_GOOD_LIST = {
    "Host":
        "api-takumi.mihoyo.com",
    "Accept":
        "application/json, text/plain, */*",
    "Origin":
        "https://user.mihoyo.com",
    "Connection":
        "keep-alive",
    "x-rpc-device_id": generate_device_id(),
    "x-rpc-client_type":
        "5",
    "User-Agent":
        conf.device_config.USER_AGENT_MOBILE,
    "Referer":
        "https://user.mihoyo.com/",
    "Accept-Language":
        "zh-CN,zh-Hans;q=0.9",
    "Accept-Encoding":
        "gzip, deflate, br"
}
HEADERS_EXCHANGE = {
    "Accept":
        "application/json, text/plain, */*",
    "Accept-Encoding":
        "gzip, deflate, br",
    "Accept-Language":
        "zh-CN,zh-Hans;q=0.9",
    "Connection":
        "keep-alive",
    "Content-Type":
        "application/json;charset=utf-8",
    "Host":
        "api-takumi.mihoyo.com",
    "User-Agent":
        conf.device_config.USER_AGENT_MOBILE,
    "x-rpc-app_version":
        conf.device_config.X_RPC_APP_VERSION,
    "x-rpc-channel":
        "appstore",
    "x-rpc-client_type":
        "1",
    "x-rpc-device_id": None,
    "x-rpc-device_model":
        conf.device_config.X_RPC_DEVICE_MODEL_MOBILE,
    "x-rpc-device_name":
        conf.device_config.X_RPC_DEVICE_NAME_MOBILE,
    "x-rpc-sys_version":
        conf.device_config.X_RPC_SYS_VERSION
}
HEADERS_ADDRESS = {
    "Host": "api-takumi.mihoyo.com",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://user.mihoyo.com",
    "Connection": "keep-alive",
    "x-rpc-device_id": None,
    "x-rpc-client_type": "5",
    "User-Agent": conf.device_config.USER_AGENT_MOBILE,
    "Referer": "https://user.mihoyo.com/",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Accept-Encoding": "gzip, deflate, br"
}

IncorrectReturn = (KeyError, TypeError, AttributeError, IndexError, ValidationError)
"""米游社API返回数据无效会触发的异常组合"""


def is_incorrect_return(exception: Exception) -> bool:
    """判断是否是米游社API返回数据无效的异常"""
    """
        return exception in IncorrectReturn or
            exception.__cause__ in IncorrectReturn or
            isinstance(exception, IncorrectReturn) or
            isinstance(exception.__cause__, IncorrectReturn)
    """
    return isinstance(exception, IncorrectReturn) or isinstance(exception.__cause__, IncorrectReturn)


class ApiResultHandler(BaseModel):
    """
    API返回的数据处理器
    """
    content: Dict[str, Any]
    """API返回的JSON对象序列化以后的Dict对象"""
    data: Optional[Dict[str, Any]]
    """API返回的数据体"""
    message: Optional[str]
    """API返回的消息内容"""
    retcode: Optional[int]
    """API返回的状态码"""

    def __init__(self, content: Dict[str, Any]):
        super().__init__(content=content)

        self.data = self.content.get("data")

        for key in ["retcode", "status"]:
            if not self.retcode:
                self.retcode = self.content.get(key)
                if not self.retcode:
                    self.retcode = self.data.get(key) if self.data else None

        self.message: Optional[str] = None
        for key in ["message", "msg"]:
            if not self.message:
                self.message = self.content.get(key)
                if not self.message:
                    self.message = self.data.get(key) if self.data else None

    @property
    def success(self):
        """
        是否成功
        """
        return self.retcode == 1 or self.message in ["成功", "OK"]

    @property
    def wrong_captcha(self):
        """
        是否返回验证码错误
        """
        return self.retcode == -201 or self.message in ["验证码错误", "Captcha not match Err"]

    @property
    def login_expired(self):
        """
        是否返回登录失效
        """
        return self.retcode in [-100, 10001] or self.message in ["登录失效，请重新登录"]

    @property
    def invalid_ds(self):
        """
        Headers里的DS是否无效
        """
        # TODO 2023/4/13: 待补充状态码
        #  return True if self.retcode == -... or self.message in ["invalid request"] else False
        return self.message in ["invalid request"]


async def get_game_record(account: UserAccount, retry: bool = True) -> Tuple[BaseApiStatus, Optional[List[GameRecord]]]:
    """
    获取用户绑定的游戏账户信息，返回一个GameRecord对象的列表

    :param account: 用户账户数据
    :param retry: 是否允许重试
    """
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_GAME_RECORD.format(account.bbs_uid), headers=HEADERS_GAME_RECORD,
                                           cookies=account.cookies.dict(), timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.login_expired:
                    logger.info(
                        f"获取用户游戏数据(GameRecord) - 用户 {account.bbs_uid} 登录失效")
                    logger.debug(f"网络请求返回: {res.text}")
                    return BaseApiStatus(login_expired=True), None
                return BaseApiStatus(success=True), list(
                    map(GameRecord.parse_obj, api_result.data["list"]))
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"获取用户游戏数据(GameRecord) - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"获取用户游戏数据(GameRecord) - 请求失败")
            return BaseApiStatus(network_error=True), None


async def get_game_list(retry: bool = True) -> Tuple[BaseApiStatus, Optional[List[GameInfo]]]:
    """
    获取米哈游游戏的详细信息，若返回`None`说明获取失败

    :param retry: 是否允许重试
    """
    headers = HEADERS_GAME_LIST.copy()
    try:
        subscribe = Subscribe()
        async for attempt in get_async_retry(retry):
            with attempt:
                headers["DS"] = generate_ds()
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_GAME_LIST, headers=headers, timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.invalid_ds:
                    logger.info(
                        f"获取游戏信息(GameInfo): DS无效，正在在线获取salt以重新生成...")
                    await subscribe.load()
                    headers["User-Agent"] = conf.device_config.USER_AGENT_MOBILE
                    headers["DS"] = generate_ds()
                return BaseApiStatus(success=True), list(
                    map(GameInfo.parse_obj, api_result.data["list"]))
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"获取游戏信息(GameInfo) - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"获取游戏信息(GameInfo) - 请求失败")
            return BaseApiStatus(network_error=True), None


async def get_user_myb(account: UserAccount, retry: bool = True) -> Tuple[BaseApiStatus, Optional[int]]:
    """
    获取用户当前米游币数量

    :param account: 用户账户数据
    :param retry: 是否允许重试
    """
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_MYB, headers=HEADERS_MYB, cookies=account.cookies.dict(),
                                           timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.login_expired:
                    logger.info(
                        f"获取用户米游币 - 用户 {account.bbs_uid} 登录失效")
                    logger.debug(f"网络请求返回: {res.text}")
                    return BaseApiStatus(login_expired=True), None
                return BaseApiStatus(success=True), int(api_result.data["points"])
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"获取用户米游币 - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"获取用户米游币 - 请求失败")
            return BaseApiStatus(network_error=True), None


async def device_login(account: UserAccount, retry: bool = True):
    """
    设备登录(deviceLogin)(适用于安卓设备)

    :param account: 用户账户数据
    :param retry: 是否允许重试
    """
    data = {
        "app_version": conf.device_config.X_RPC_APP_VERSION,
        "device_id": account.device_id_android,
        "device_name": conf.device_config.X_RPC_DEVICE_NAME_ANDROID,
        "os_version": "30",
        "platform": "Android",
        "registration_id": "1a0018970a5c00e814d"
    }
    headers = HEADERS_DEVICE.copy()
    headers["x-rpc-device_id"] = account.device_id_android
    try:
        subscribe = Subscribe()
        async for attempt in get_async_retry(retry):
            with attempt:
                headers["DS"] = generate_ds(data)
                async with httpx.AsyncClient() as client:
                    res = await client.post(URL_DEVICE_LOGIN, headers=headers, json=data,
                                            cookies=account.cookies.dict(),
                                            timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.login_expired:
                    logger.info(
                        f"设备登录(device_login) - 用户 {account.bbs_uid} 登录失效")
                    logger.debug(f"网络请求返回: {res.text}")
                    return BaseApiStatus(login_expired=True)
                if api_result.invalid_ds:
                    logger.info(
                        f"设备登录(device_login): DS无效，正在在线获取salt以重新生成...")
                    await subscribe.load()
                    headers["DS"] = generate_ds(data)
                if res.json()["message"] != "OK":
                    raise ValueError
                else:
                    return BaseApiStatus(success=True)
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"设备登录(device_login) - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True)
        else:
            logger.exception(f"设备登录(device_login) - 请求失败")
            return BaseApiStatus(network_error=True)


async def device_save(account: UserAccount, retry: bool = True):
    """
    设备保存(saveDevice)(适用于安卓设备)

    :param account: 用户账户数据
    :param retry: 是否允许重试
    """
    data = {
        "app_version": conf.device_config.X_RPC_APP_VERSION,
        "device_id": account.device_id_android,
        "device_name": conf.device_config.X_RPC_DEVICE_NAME_ANDROID,
        "os_version": "30",
        "platform": "Android",
        "registration_id": "1a0018970a5c00e814d"
    }
    headers = HEADERS_DEVICE.copy()
    headers["x-rpc-device_id"] = account.device_id_android
    try:
        subscribe = Subscribe()
        async for attempt in get_async_retry(retry):
            with attempt:
                headers["DS"] = generate_ds(data)
                async with httpx.AsyncClient() as client:
                    res = await client.post(URL_DEVICE_SAVE, headers=headers, json=data, cookies=account.cookies.dict(),
                                            timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.login_expired:
                    logger.info(
                        f"设备保存(device_save) - 用户 {account.bbs_uid} 登录失效")
                    logger.debug(f"网络请求返回: {res.text}")
                    return BaseApiStatus(login_expired=True)
                if api_result.invalid_ds:
                    logger.info(
                        f"设备保存(device_save): DS无效，正在在线获取salt以重新生成...")
                    await subscribe.load()
                if res.json()["message"] != "OK":
                    raise ValueError
                else:
                    return BaseApiStatus(success=True)
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"设备保存(device_save) - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True)
        else:
            logger.exception(f"设备保存(device_save) - 请求失败")
            return BaseApiStatus(network_error=True)


async def get_good_detail(good: Union[Good, str], retry: bool = True) -> Tuple[GetGoodDetailStatus, Optional[Good]]:
    """
    获取某商品的详细信息

    :param good: 商品对象 / 商品ID，如果指定为商品对象，则会更新商品对象的数据并返回其引用
    :param retry: 是否允许重试
    :return: 商品数据
    """
    good_id = good.goods_id if isinstance(good, Good) else good
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_CHECK_GOOD.format(good_id), timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                # TODO 2023/4/13: 待改成对象方法判断
                if api_result.message == '商品不存在' or api_result.message == '商品已下架':
                    return GetGoodDetailStatus(good_not_existed=True), None
                if isinstance(good, Good):
                    return GetGoodDetailStatus(success=True), good.update(api_result.data)
                else:
                    return GetGoodDetailStatus(success=True), Good.parse_obj(api_result.data)
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"米游币商品兑换 - 获取商品详细信息: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetGoodDetailStatus(incorrect_return=True), None
        else:
            logger.exception(f"米游币商品兑换 - 获取商品详细信息: 网络请求失败")
            return GetGoodDetailStatus(network_error=True), None


async def get_good_games(retry: bool = True) -> Tuple[BaseApiStatus, Optional[List[Tuple[str, str]]]]:
    """
    获取商品分区列表

    :param retry: 是否允许重试
    :return: (商品分区全名, 字母简称) 的列表
    """
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_GOOD_LIST.format(page=1,
                                                                game=""),
                                           headers=HEADERS_GOOD_LIST,
                                           timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                return BaseApiStatus(success=True), list(map(lambda x: (x["name"], x["key"]), api_result.data["games"]))
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"米游币商品兑换 - 获取商品列表: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"米游币商品兑换 - 获取商品列表: 网络请求失败")
            return BaseApiStatus(network_error=True), None


async def get_good_list(game: str = "", retry: bool = True) -> Tuple[
    BaseApiStatus, Optional[List[Good]]]:
    """
    获取商品信息列表

    :param game: 游戏简称（默认为空，即获取所有游戏的商品）
    :param retry: 是否允许重试
    :return: 商品信息列表
    """
    good_list = []
    page = 1

    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_GOOD_LIST.format(page=page,
                                                                game=game), headers=HEADERS_GOOD_LIST,
                                           timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                goods = map(Good.parse_obj, api_result.data["list"])
                # 判断是否已经读完所有商品
                if not goods:
                    break
                else:
                    good_list += goods
                page += 1
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"米游币商品兑换 - 获取商品列表: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"米游币商品兑换 - 获取商品列表: 网络请求失败")
            return BaseApiStatus(network_error=True), None

    return BaseApiStatus(success=True), good_list


async def get_address(account: UserAccount, retry: bool = True) -> Tuple[BaseApiStatus, Optional[List[Address]]]:
    """
    获取用户的地址数据

    :param account: 用户账户数据
    :param retry: 是否允许重试
    """
    headers = HEADERS_ADDRESS.copy()
    headers["x-rpc-device_id"] = account.device_id_ios
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_ADDRESS.format(
                        round(NtpTime.time() * 1000)), headers=headers, cookies=account.cookies.dict(),
                        timeout=conf.preference.timeout)
                    api_result = ApiResultHandler(res.json())
                    if api_result.login_expired:
                        logger.info(
                            f"获取地址数据 - 用户 {account.bbs_uid} 登录失效")
                        logger.debug(f"网络请求返回: {res.text}")
                        return BaseApiStatus(login_expired=True), None
                address_list = list(map(Address.parse_obj, api_result.data["list"]))
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"获取地址数据 - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"获取地址数据 - 请求失败")
            return BaseApiStatus(network_error=True), None
    return BaseApiStatus(success=True), address_list


async def check_registrable(phone_number: int, retry: bool = True) -> Tuple[BaseApiStatus, Optional[bool]]:
    """
    检查用户是否可以注册

    :param phone_number: 手机号
    :param retry: 是否允许重试
    """
    headers = HEADERS_WEBAPI.copy()
    headers["x-rpc-device_id"] = generate_device_id()
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(URL_REGISTRABLE.format(mobile=phone_number, t=round(NtpTime.time() * 1000)),
                                           headers=headers, timeout=conf.preference.timeout)
                    api_result = ApiResultHandler(res.json())
                return BaseApiStatus(success=True), bool(api_result.data["is_registable"])
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"检查用户 {phone_number} 是否可以注册 - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None
        else:
            logger.exception(f"检查用户 {phone_number} 是否可以注册 - 请求失败")
            return BaseApiStatus(network_error=True), None


async def create_mmt(keep_client: bool = False, retry: bool = True) -> Tuple[
    BaseApiStatus, Optional[MmtData], Optional[httpx.AsyncClient]]:
    """
    发送短信验证前所需的人机验证任务申请

    :param keep_client: httpx.AsyncClient 连接是否需要关闭
    :param retry: 是否允许重试
    """
    headers = HEADERS_WEBAPI.copy()
    headers["x-rpc-device_id"] = generate_device_id()

    async def request():
        """
        发送请求的闭包函数
        """
        time_now = round(NtpTime.time() * 1000)
        await client.options(URL_CREATE_MMT.format(now=time_now, t=time_now),
                             headers=headers, timeout=conf.preference.timeout)
        return await client.get(URL_CREATE_MMT.format(now=time_now, t=time_now),
                                headers=headers, timeout=conf.preference.timeout)

    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                if keep_client:
                    client = httpx.AsyncClient()
                    res = await request()
                else:
                    async with httpx.AsyncClient() as client:
                        res = await request()
                api_result = ApiResultHandler(res.json())
                return BaseApiStatus(success=True), MmtData.parse_obj(api_result.data["mmt_data"]), client
    except tenacity.RetryError as e:
        if keep_client:
            await client.aclose()
        if is_incorrect_return(e):
            logger.exception(f"获取短信验证-人机验证任务(create_mmt) - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return BaseApiStatus(incorrect_return=True), None, client
        else:
            logger.exception(f"获取短信验证-人机验证任务(create_mmt) - 请求失败")
            return BaseApiStatus(network_error=True), None, None
    except ConnectError:
        if keep_client:
            await client.aclose()
        logger.exception(f"获取短信验证-人机验证任务(create_mmt) - 网络连接失败")
        return BaseApiStatus(network_error=True), None, None


async def create_mobile_captcha(phone_number: int,
                                mmt_data: MmtData,
                                geetest_result: GeetestResult,
                                client: Optional[httpx.AsyncClient] = None,
                                retry: bool = True
                                ) -> Tuple[CreateMobileCaptchaStatus, Optional[httpx.AsyncClient]]:
    """
    发送短信验证码

    :param phone_number: 手机号
    :param mmt_data: 人机验证任务数据
    :param geetest_result: 人机验证结果数据
    :param client: httpx.AsyncClient 连接
    :param retry: 是否允许重试
    """
    headers = HEADERS_WEBAPI.copy()
    headers["x-rpc-device_id"] = generate_device_id()
    params = {
        "action_type": "login",
        "mmt_key": mmt_data.mmt_key,
        "geetest_challenge": mmt_data.challenge,
        "geetest_validate": geetest_result.validate,
        "geetest_seccode": geetest_result.seccode,
        "mobile": phone_number,
        "t": round(NtpTime.time() * 1000)
    }
    encoded_params = urlencode(params)

    async def request():
        """
        发送请求的闭包函数
        """
        return await client.post(URL_CREATE_MOBILE_CAPTCHA,
                                 content=encoded_params,
                                 headers=headers,
                                 timeout=conf.preference.timeout)

    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                # FIXME 2023/4/13: 似乎会导致卡在连接状态，暂时弃用
                #   res = await client.options(URL_CREATE_MOBILE_CAPTCHA,
                #                            headers=headers,
                #                            timeout=conf.preference.timeout)
                #   cookies.update(res.cookies)
                if client is not None:
                    res = await request()
                else:
                    async with httpx.AsyncClient() as client:
                        res = await request()
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    return CreateMobileCaptchaStatus(success=True), client
                elif api_result.wrong_captcha:
                    return CreateMobileCaptchaStatus(incorrect_geetest=True), client
    except tenacity.RetryError as e:
        if client:
            await client.aclose()
        if is_incorrect_return(e):
            logger.exception(f"发送短信验证码 - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return CreateMobileCaptchaStatus(incorrect_return=True), client
        else:
            logger.exception(f"发送短信验证码 - 请求失败")
            return CreateMobileCaptchaStatus(network_error=True), None


async def get_login_ticket_by_captcha(phone_number: str,
                                      captcha: int,
                                      client: Optional[httpx.AsyncClient] = None,
                                      retry: bool = True) -> \
        Tuple[
            GetCookieStatus, Optional[BBSCookies]]:
    """
    通过短信验证码获取 login_ticket

    :param phone_number: 手机号
    :param captcha: 短信验证码
    :param client: httpx.AsyncClient 连接
    :param retry: 是否允许重试

    >>> import asyncio
    >>> coroutine = get_cookie_token_by_captcha("12345678910", 123456)
    >>> assert asyncio.new_event_loop().run_until_complete(coroutine)[0].incorrect_captcha is True
    """

    headers = HEADERS_WEBAPI.copy()
    headers["x-rpc-device_id"] = generate_device_id()
    params = {
        "mobile": phone_number,
        "mobile_captcha": captcha,
        "source": "user.mihoyo.com",
        "t": round(NtpTime.time() * 1000),
    }
    encoded_params = urlencode(params)

    async def request():
        """
        发送请求的闭包函数
        """
        _cookies = {}
        _res = await client.options(URL_LOGIN_TICKET_BY_CAPTCHA,
                                    headers=headers,
                                    timeout=conf.preference.timeout
                                    )
        _cookies.update(_res.cookies)
        return await client.post(URL_LOGIN_TICKET_BY_CAPTCHA,
                                 headers=headers,
                                 content=encoded_params,
                                 cookies=_cookies,
                                 timeout=conf.preference.timeout
                                 )

    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                if client is not None:
                    res = await request()
                else:
                    async with httpx.AsyncClient() as client:
                        res = await request()
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    cookies = BBSCookies.parse_obj(dict_from_cookiejar(
                        res.cookies.jar))
                    if not cookies.login_ticket:
                        return GetCookieStatus(missing_login_ticket=True), None
                    else:
                        if client:
                            await client.aclose()
                        return GetCookieStatus(success=True), cookies
                elif api_result.wrong_captcha:
                    logger.info(
                        f"通过短信验证码获取 login_ticket - 验证码错误，但你可以再次尝试登录")
                    return GetCookieStatus(incorrect_captcha=True), None
                else:
                    raise IncorrectReturn
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过短信验证码获取 login_ticket: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过短信验证码获取 login_ticket: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def get_multi_token_by_login_ticket(cookies: BBSCookies, retry: bool = True) -> Tuple[
    GetCookieStatus, Optional[BBSCookies]]:
    """
    通过 login_ticket 获取 `stoken 和 ltoken

    :param cookies: 米游社Cookies，需要包含 login_ticket 和 bbs_uid
    :param retry: 是否允许重试
    """
    if not cookies.login_ticket:
        return GetCookieStatus(missing_login_ticket=True), None
    elif not cookies.bbs_uid:
        return GetCookieStatus(missing_bbs_uid=True), None
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        URL_MULTI_TOKEN_BY_LOGIN_TICKET.format(cookies.login_ticket, cookies.bbs_uid),
                        headers=HEADERS_API_TAKUMI_PC,
                        timeout=conf.preference.timeout)
                api_result = ApiResultHandler(res.json())
                if api_result.login_expired:
                    logger.warning(f"通过 login_ticket 获取 stoken: 登录失效")
                    return GetCookieStatus(login_expired=True), None
                else:
                    cookies.stoken = list(filter(
                        lambda x: x["name"] == "stoken", api_result.data["list"]))[0]["token"]
                    cookies.ltoken = list(filter(
                        lambda x: x["name"] == "ltoken", api_result.data["list"]))[0]["token"]
                    return GetCookieStatus(success=True), cookies
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过 login_ticket 获取 stoken: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过 login_ticket 获取 stoken: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def get_cookie_token_by_captcha(phone_number: str, captcha: int, retry: bool = True) -> Tuple[
    GetCookieStatus, Optional[BBSCookies]]:
    """
    通过短信验证码获取 cookie_token

    :param phone_number: 手机号
    :param captcha: 验证码
    :param retry: 是否允许重试

    >>> import asyncio
    >>> coroutine = get_cookie_token_by_captcha("12345678910", 123456)
    >>> assert asyncio.new_event_loop().run_until_complete(coroutine)[0].incorrect_captcha is True
    """
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.post(URL_COOKIE_TOKEN_BY_CAPTCHA,
                                            headers=HEADERS_API_TAKUMI_PC,
                                            json={
                                                "is_bh2": False,
                                                "mobile": phone_number,
                                                "captcha": str(captcha),
                                                "action_type": "login",
                                                "token_type": 6
                                            },
                                            timeout=conf.preference.timeout
                                            )
                api_result = ApiResultHandler(res.json())
                if api_result.wrong_captcha:
                    logger.info(f"登录米哈游账号 - 验证码错误")
                    return GetCookieStatus(incorrect_captcha=True), None
                else:
                    cookies = BBSCookies.parse_obj(dict_from_cookiejar(res.cookies.jar))
                    if not cookies.cookie_token:
                        return GetCookieStatus(missing_cookie_token=True), None
                    elif not cookies.bbs_uid:
                        return GetCookieStatus(missing_bbs_uid=True), None
                    else:
                        return GetCookieStatus(success=True), cookies
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过短信验证码获取 cookie_token: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过短信验证码获取 cookie_token: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def get_login_ticket_by_password(account: str, password: str, mmt_data: MmtData, geetest_result: GeetestResult,
                                       retry: bool = True) -> Tuple[GetCookieStatus, Optional[BBSCookies]]:
    """
    使用密码登录获取login_ticket

    :param account: 账号
    :param password: 密码
    :param mmt_data: GEETEST验证任务数据
    :param geetest_result: GEETEST验证结果数据
    :param retry: 是否允许重试
    """
    headers = HEADERS_WEBAPI.copy()
    headers["x-rpc-device_id"] = generate_device_id()
    params = {
        "account": account,
        "password": password,
        "is_crypto": False,
        "mmt_key": mmt_data.mmt_key,
        "geetest_challenge": mmt_data.challenge,
        "geetest_validate": geetest_result.validate,
        "geetest_seccode": geetest_result.seccode,
        "source": "user.mihoyo.com",
        "t": round(NtpTime.time() * 1000)
    }
    encoded_params = urlencode(params)
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        URL_LOGIN_TICKET_BY_PASSWORD,
                        content=encoded_params,
                        headers=headers,
                        timeout=conf.preference.timeout
                    )
                cookies = BBSCookies.parse_obj(dict_from_cookiejar(res.cookies.jar))
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    return GetCookieStatus(success=True), cookies
                elif api_result.wrong_captcha:
                    logger.warning(f"使用密码登录获取login_ticket - 图片验证码失败")
                    return GetCookieStatus(incorrect_captcha=True), None
    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"使用密码登录获取login_ticket - 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"使用密码登录获取login_ticket - 请求失败")
            return GetCookieStatus(network_error=True), None


async def get_cookie_token_by_stoken(cookies: BBSCookies, device_id: Optional[str] = None, retry: bool = True) -> Tuple[
    GetCookieStatus, Optional[BBSCookies]]:
    """
    通过 stoken_v2 获取 cookie_token

    :param cookies: 米游社Cookies，需要包含 stoken_v2 和 mid
    :param device_id: X_RPC_DEVICE_ID
    :param retry: 是否允许重试

    >>> import asyncio
    >>> coroutine = get_cookie_token_by_stoken(BBSCookies())
    >>> assert asyncio.new_event_loop().run_until_complete(coroutine)[0].success is False
    """
    headers = HEADERS_PASSPORT_API.copy()
    headers["x-rpc-device_id"] = device_id if device_id else generate_device_id()
    if not cookies.stoken_v2:
        return GetCookieStatus(missing_stoken_v2=True), None
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        URL_COOKIE_TOKEN_BY_STOKEN,
                        cookies=cookies.dict(v2_stoken=True, cookie_type=True),
                        headers=headers,
                        timeout=conf.preference.timeout
                    )
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    cookies.cookie_token = api_result.data["cookie_token"]
                    if not cookies.bbs_uid:
                        cookies.bbs_uid = api_result.data["uid"]
                    return GetCookieStatus(success=True), cookies
                elif api_result.login_expired:
                    logger.warning(f"通过 stoken 获取 cookie_token: 登录失效")
                    return GetCookieStatus(login_expired=True), None
                else:
                    raise IncorrectReturn

    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过 stoken 获取 cookie_token: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过 stoken 获取 cookie_token: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def get_stoken_v2_by_v1(cookies: BBSCookies, device_id: Optional[str] = None, retry: bool = True) -> Tuple[
    GetCookieStatus, Optional[BBSCookies]]:
    """
    通过 stoken_v1 获取 stoken_v2 以及 mid

    :param cookies: 米游社Cookies，需要包含 stoken_v1
    :param device_id: X_RPC_DEVICE_ID
    :param retry: 是否允许重试

    >>> import asyncio
    >>> coroutine = get_stoken_v2_by_v1(BBSCookies())
    >>> assert asyncio.new_event_loop().run_until_complete(coroutine)[0].success is False
    """
    headers = HEADERS_PASSPORT_API.copy()
    headers["x-rpc-device_id"] = device_id if device_id else generate_device_id()
    headers.setdefault("x-rpc-aigis", "")
    headers.setdefault("x-rpc-app_id", "bll8iq97cem8")

    if not cookies.stoken_v1:
        return GetCookieStatus(missing_stoken_v1=True), None
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    headers.setdefault("DS", generate_ds(salt=conf.salt_config.SALT_PROD))
                    res = await client.post(
                        URL_STOKEN_V2_BY_V1,
                        cookies={"stoken": cookies.stoken_v1, "stuid": cookies.bbs_uid},
                        headers=headers,
                        timeout=conf.preference.timeout
                    )
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    cookies.stoken_v2 = api_result.data["token"]["token"]
                    cookies.mid = api_result.data["user_info"]["mid"]
                    if not cookies.bbs_uid:
                        cookies.bbs_uid = api_result.data["user_info"]["aid"]
                    return GetCookieStatus(success=True), cookies
                elif api_result.login_expired:
                    logger.warning(f"通过 stoken_v1 获取 stoken_v2: 登录失效")
                    return GetCookieStatus(login_expired=True), None
                else:
                    raise IncorrectReturn

    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过 stoken_v1 获取 stoken_v2: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过 stoken_v1 获取 stoken_v2: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def get_ltoken_by_stoken(cookies: BBSCookies, device_id: Optional[str] = None, retry: bool = True) -> Tuple[
    GetCookieStatus, Optional[BBSCookies]]:
    """
    通过 stoken_v2 和 mid 获取 ltoken

    :param cookies: 米游社Cookies，需要包含 stoken_v2 和 mid
    :param device_id: X_RPC_DEVICE_ID
    :param retry: 是否允许重试

    >>> import asyncio
    >>> coroutine = get_ltoken_by_stoken(BBSCookies())
    >>> assert asyncio.new_event_loop().run_until_complete(coroutine)[0].success is False
    """
    headers = HEADERS_PASSPORT_API.copy()
    headers["x-rpc-device_id"] = device_id if device_id else generate_device_id()
    if not cookies.stoken_v2:
        return GetCookieStatus(missing_stoken_v2=True), None
    if not cookies.mid:
        return GetCookieStatus(missing_mid=True), None
    try:
        async for attempt in get_async_retry(retry):
            with attempt:
                async with httpx.AsyncClient() as client:
                    res = await client.get(
                        URL_LTOKEN_BY_STOKEN,
                        cookies=cookies.dict(v2_stoken=True, cookie_type=True),
                        headers=headers,
                        timeout=conf.preference.timeout
                    )
                api_result = ApiResultHandler(res.json())
                if api_result.success:
                    cookies.ltoken = api_result.data["ltoken"]
                    return GetCookieStatus(success=True), cookies
                elif api_result.login_expired:
                    logger.warning(f"通过 stoken 获取 ltoken: 登录失效")
                    return GetCookieStatus(login_expired=True), None
                else:
                    raise IncorrectReturn

    except tenacity.RetryError as e:
        if is_incorrect_return(e):
            logger.exception(f"通过 stoken 获取 ltoken: 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return GetCookieStatus(incorrect_return=True), None
        else:
            logger.exception(f"通过 stoken 获取 ltoken: 网络请求失败")
            return GetCookieStatus(network_error=True), None


async def good_exchange(plan: ExchangePlan) -> Tuple[ExchangeStatus, Optional[ExchangeResult]]:
    """
    执行米游币商品兑换

    :param plan: 兑换计划
    """
    headers = HEADERS_EXCHANGE
    headers["x-rpc-device_id"] = plan.account.device_id_ios
    content = {
        "app_id": 1,
        "point_sn": "myb",
        "goods_id": plan.good.goods_id,
        "exchange_num": 1,
    }
    if plan.address is not None:
        content.setdefault("address_id", plan.address.id)
    if plan.game_record is not None:
        content.setdefault("uid", plan.game_record.game_role_id)
        # 例: cn_gf01
        content.setdefault("region", plan.game_record.region)
        # 例: hk4e_cn
        content.setdefault("game_biz", plan.good.game_biz)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                URL_EXCHANGE, headers=headers, json=content, cookies=plan.account.cookies.dict(),
                timeout=conf.preference.timeout)
        api_result = ApiResultHandler(res.json())
        if api_result.login_expired:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 登录失效")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(login_expired=True), None
        if api_result.success:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 兑换成功！可以自行确认。")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(success=True), ExchangeResult(result=True, return_data=res.json(), plan=plan)
        else:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 兑换失败，可以自行确认。")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(success=True), ExchangeResult(result=False, return_data=res.json(), plan=plan)
    except Exception as e:
        if is_incorrect_return(e):
            logger.error(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(incorrect_return=True), None
        else:
            logger.exception(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 请求失败")
            return ExchangeStatus(network_error=True), None


def good_exchange_sync(plan: ExchangePlan) -> Tuple[ExchangeStatus, Optional[ExchangeResult]]:
    """
    执行米游币商品兑换

    :param plan: 兑换计划
    """
    headers = HEADERS_EXCHANGE
    headers["x-rpc-device_id"] = plan.account.device_id_ios
    content = {
        "app_id": 1,
        "point_sn": "myb",
        "goods_id": plan.good.goods_id,
        "exchange_num": 1,
    }
    if plan.address is not None:
        content.setdefault("address_id", plan.address.id)
    if plan.game_record is not None:
        content.setdefault("uid", plan.game_record.game_role_id)
        # 例: cn_gf01
        content.setdefault("region", plan.game_record.region)
        # 例: hk4e_cn
        content.setdefault("game_biz", plan.good.game_biz)
    try:
        with httpx.Client() as client:
            res = client.post(
                URL_EXCHANGE, headers=headers, json=content, cookies=plan.account.cookies.dict(),
                timeout=conf.preference.timeout)
        api_result = ApiResultHandler(res.json())
        if api_result.login_expired:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 登录失效")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(login_expired=True), None
        if api_result.success:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 兑换成功！可以自行确认。")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(success=True), ExchangeResult(result=True, return_data=res.json(), plan=plan)
        else:
            logger.info(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 兑换失败，可以自行确认。")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(success=True), ExchangeResult(result=False, return_data=res.json(), plan=plan)
    except Exception as e:
        if is_incorrect_return(e):
            logger.error(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 服务器没有正确返回")
            logger.debug(f"网络请求返回: {res.text}")
            return ExchangeStatus(incorrect_return=True), None
        else:
            logger.exception(
                f"米游币商品兑换 - 执行兑换: 用户 {plan.account.bbs_uid} 商品 {plan.good.goods_id} 请求失败")
            return ExchangeStatus(network_error=True), None
