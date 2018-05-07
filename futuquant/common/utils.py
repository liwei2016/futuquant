# -*- coding: utf-8 -*-

import hashlib
import json
import os
import sys
import socket
import traceback
from datetime import datetime
from struct import calcsize
from google.protobuf.json_format import MessageToJson
from threading import RLock
import struct
import time

from futuquant.common.constant import *
from futuquant.common.pbjson import json2pb
from futuquant.common.ft_logger import logger


def set_proto_fmt(proto_fmt):
    """Set communication protocol format, json ans protobuf supported"""
    os.environ['FT_PROTO_FMT'] = str(proto_fmt)


def get_proto_fmt():
    return int(os.environ['FT_PROTO_FMT']) if 'FT_PROTO_FMT' in os.environ else DEFULAT_PROTO_FMT


def get_client_ver():
    return CLIENT_VERSION


def get_client_id():
    return int(os.environ['CLIENT_ID']) if 'CLIENT_ID' in os.environ else DEFULAT_CLIENT_ID


def set_client_id(client_id):
    os.environ['CLIENT_ID'] = str(client_id)


def get_message_head_len():
    return calcsize(MESSAGE_HEAD_FMT)


def check_date_str_format(s):
    """Check the format of date string"""
    try:
        if ":" not in s:
            _ = datetime.strptime(s, "%Y-%m-%d")
        else:
            _ = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return RET_OK, None
    except ValueError:
        traceback.print_exc()
        err = sys.exc_info()[1]
        error_str = ERROR_STR_PREFIX + str(err)
        return RET_ERROR, error_str


def extract_pls_rsp(rsp_str):
    """Extract the response of PLS"""
    try:
        rsp = json.loads(rsp_str)
    except ValueError:
        traceback.print_exc()
        err = sys.exc_info()[1]
        err_str = ERROR_STR_PREFIX + str(err)
        return RET_ERROR, err_str, None

    error_code = int(rsp['retType'])

    if error_code != 1:
        error_str = ERROR_STR_PREFIX + rsp['retMsg']
        return RET_ERROR, error_str, None

    return RET_OK, "", rsp


def normalize_date_format(date_str):
    """normalize the format of data"""
    if ":" not in date_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

    ret = date_obj.strftime("%Y-%m-%d")
    return ret


def split_stock_str(stock_str_param):
    """split the stock string"""
    stock_str = str(stock_str_param)

    split_loc = stock_str.find(".")
    '''do not use the built-in split function in python.
    The built-in function cannot handle some stock strings correctly.
    for instance, US..DJI, where the dot . itself is a part of original code'''
    if 0 <= split_loc < len(
            stock_str) - 1 and stock_str[0:split_loc] in MKT_MAP:
        market_str = stock_str[0:split_loc]
        market_code = MKT_MAP[market_str]
        partial_stock_str = stock_str[split_loc + 1:]
        return RET_OK, (market_code, partial_stock_str)

    else:
        error_str = ERROR_STR_PREFIX + "format of %s is wrong. (US.AAPL, HK.00700, SZ.000001)" % stock_str
        return RET_ERROR, error_str


def merge_qot_mkt_stock_str(qot_mkt, partial_stock_str):
    """
    Merge the string of stocks
    :param market: market code
    :param partial_stock_str: original stock code string. i.e. "AAPL","00700", "000001"
    :return: unified representation of a stock code. i.e. "US.AAPL", "HK.00700", "SZ.000001"

    """
    market_str = QUOTE.REV_MKT_MAP[qot_mkt]
    stock_str = '.'.join([market_str, partial_stock_str])
    return stock_str


def merge_trd_mkt_stock_str(trd_mkt, partial_stock_str):
    """
    Merge the string of stocks
    :param market: market code
    :param partial_stock_str: original stock code string. i.e. "AAPL","00700", "000001"
    :return: unified representation of a stock code. i.e. "US.AAPL", "HK.00700", "SZ.000001"

    """
    mkt_qot = Market.NONE
    mkt = TRADE.REV_TRD_MKT_MAP[trd_mkt] if trd_mkt in TRADE.REV_TRD_MKT_MAP else TrdMarket.NONE
    if mkt == TrdMarket.HK:
        mkt_qot = Market.HK
    elif mkt == TrdMarket.US:
        mkt_qot = Market.US
    else: # mkt == TrdMarket.CN or mt == TrdMarket.HKCC: 暂时不支持
        raise Exception("merge_trd_mkt_stock_str: unknown trd_mkt.")

    return merge_qot_mkt_stock_str(MKT_MAP[mkt_qot], partial_stock_str)


def str2binary(s):
    """
    Transfer string to binary
    :param s: string content to be transformed to binary
    :return: binary
    """
    return s.encode('utf-8')


def is_str(obj):
    if sys.version_info.major == 3:
        return isinstance(obj, str) or isinstance(obj, bytes)
    else:
        return isinstance(obj, basestring)


def price_to_str_int1000(price):
    return str(int(round(float(price) * 1000,
                         0))) if str(price) is not '' else ''


# 1000*int price to float val
def int1000_price_to_float(price):
    return round(float(price) / 1000.0,
                 3) if str(price) is not '' else float(0)


# 10^9 int price to float val
def int10_9_price_to_float(price):
    return round(float(price) / float(10**9),
                 3) if str(price) is not '' else float(0)


# list 参数除重及规整
def unique_and_normalize_list(lst):
    ret = []
    if not lst:
        return ret
    tmp = lst if isinstance(lst, list) else [lst]
    [ret.append(x) for x in tmp if x not in ret]
    return ret


def md5_transform(raw_str):
    h1 = hashlib.md5()
    h1.update(raw_str.encode(encoding='utf-8'))
    return h1.hexdigest()


g_unique_id = int(time.time() % 10000)
g_unique_lock = RLock()
def get_unique_id32():
    global g_unique_id
    with g_unique_lock:
        g_unique_id += 1
        if g_unique_id >= 4294967295:
            g_unique_id = int(time.time() % 10000)
        ret_id = g_unique_id
    return ret_id


class ProtobufMap(dict):
    created_protobuf_map = {}

    def __init__(self):

        """ InitConnect = 1001  # 初始化连接 """
        from futuquant.common.pb.InitConnect_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.InitConnect] = Response()

        """ GlobalState = 1002  # 获取全局状态 """
        from futuquant.common.pb.GlobalState_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.GlobalState] = Response()

        """ PushNotify = 1003  # 通知推送 """
        from futuquant.common.pb.PushNotify_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.PushNotify] = Response()

        """ PushHeartBeat = 1004  # 通知推送 """
        from futuquant.common.pb.PushHeartBeat_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.PushHeartBeat] = Response()

        """ Trd_GetAccList = 2001  # 获取业务账户列表 """
        from futuquant.common.pb.Trd_GetAccList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetAccList] = Response()

        """ Trd_UnlockTrade = 2005  # 解锁或锁定交易 """
        from futuquant.common.pb.Trd_UnlockTrade_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_UnlockTrade] = Response()

        """ Trd_SubAccPush = 2008  # 订阅业务账户的交易推送数据 """
        from futuquant.common.pb.Trd_SubAccPush_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_SubAccPush] = Response()

        """  Trd_GetFunds = 2101  # 获取账户资金 """
        from futuquant.common.pb.Trd_GetFunds_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetFunds] = Response()

        """ Trd_GetPositionList = 2102  # 获取账户持仓 """
        from futuquant.common.pb.Trd_GetPositionList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetPositionList] = Response()

        """ Trd_GetOrderList = 2201  # 获取订单列表 """
        from futuquant.common.pb.Trd_GetOrderList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetOrderList] = Response()

        """ Trd_PlaceOrder = 2202  # 下单 """
        from futuquant.common.pb.Trd_PlaceOrder_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_PlaceOrder] = Response()

        """ Trd_ModifyOrder = 2205  # 修改订单 """
        from futuquant.common.pb.Trd_ModifyOrder_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_ModifyOrder] = Response()

        """ Trd_UpdateOrder = 2208  # 订单状态变动通知(推送) """
        from futuquant.common.pb.Trd_UpdateOrder_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_UpdateOrder] = Response()

        """ Trd_GetOrderFillList = 2211  # 获取成交列表 """
        from futuquant.common.pb.Trd_GetOrderFillList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetOrderFillList] = Response()

        """ Trd_UpdateOrderFill = 2218  # 成交通知(推送) """
        from  futuquant.common.pb.Trd_UpdateOrderFill_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_UpdateOrderFill] = Response()

        """ Trd_GetHistoryOrderList = 2221  # 获取历史订单列表 """
        from futuquant.common.pb.Trd_GetHistoryOrderList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetHistoryOrderList] = Response()

        """ Trd_GetHistoryOrderFillList = 2222  # 获取历史成交列表 """
        from futuquant.common.pb.Trd_GetHistoryOrderFillList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Trd_GetHistoryOrderFillList] = Response()

        """ Qot_Sub = 3001  # 订阅或者反订阅 """
        from futuquant.common.pb.Qot_Sub_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_Sub] = Response()

        """ Qot_RegQotPush = 3002  # 注册推送 """
        from futuquant.common.pb.Qot_RegQotPush_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_RegQotPush] = Response()

        """ Qot_ReqSubInfo = 3003  # 获取订阅信息 """
        from futuquant.common.pb.Qot_ReqSubInfo_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqSubInfo] = Response()

        """ Qot_ReqStockBasic = 3004  # 获取股票基本行情 """
        from futuquant.common.pb.Qot_ReqStockBasic_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqStockBasic] = Response()

        """ Qot_PushStockBasic = 3005  # 推送股票基本行情 """
        from futuquant.common.pb.Qot_PushStockBasic_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushStockBasic] = Response()

        """ Qot_ReqKL = 3006  # 获取K线 """
        from futuquant.common.pb.Qot_ReqKL_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqKL] = Response()

        """ Qot_PushKL = 3007  # 推送K线 """
        from futuquant.common.pb.Qot_PushKL_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushKL] = Response()

        """ Qot_ReqRT = 3008  # 获取分时 """
        from futuquant.common.pb.Qot_ReqRT_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqRT] = Response()

        """ Qot_PushRT = 3009  # 推送分时 """
        from futuquant.common.pb.Qot_PushRT_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushRT] = Response()

        """ Qot_ReqTicker = 3010  # 获取逐笔 """
        from futuquant.common.pb.Qot_ReqTicker_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqTicker] = Response()

        """ Qot_PushTicker = 3011  # 推送逐笔 """
        from futuquant.common.pb.Qot_PushTicker_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushTicker] = Response()

        """ Qot_ReqOrderBook = 3012  # 获取买卖盘 """
        from futuquant.common.pb.Qot_ReqOrderBook_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqOrderBook] = Response()

        """ Qot_PushOrderBook = 3013  # 推送买卖盘 """
        from futuquant.common.pb.Qot_PushOrderBook_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushOrderBook] = Response()

        """ Qot_ReqBroker = 3014  # 获取经纪队列 """
        from futuquant.common.pb.Qot_ReqBroker_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqBroker] = Response()

        """ Qot_PushBroker = 3015  # 推送经纪队列 """
        from futuquant.common.pb.Qot_PushBroker_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_PushBroker] = Response()

        """ Qot_ReqHistoryKL = 3100  # 获取历史K线 """
        from futuquant.common.pb.Qot_HistoryKL_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqHistoryKL] = Response()

        """ Qot_ReqHistoryKLPoints = 3101  # 获取多只股票历史单点K线 """
        from futuquant.common.pb.Qot_HistoryKLPoints_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqHistoryKLPoints] = Response()

        """ Qot_ReqRehab = 3102  # 获取复权信息 """
        from futuquant.common.pb.Qot_ReqRehab_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqRehab] = Response()

        """ Qot_ReqTradeDate = 3200  # 获取市场交易日 """
        from futuquant.common.pb.Qot_ReqTradeDate_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqTradeDate] = Response()

        """ Qot_ReqSuspend = 3201  # 获取股票停牌信息 """
        from futuquant.common.pb.Qot_ReqSuspend_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqSuspend] = Response()

        """ Qot_ReqStockList = 3202  # 获取股票列表 """
        from futuquant.common.pb.Qot_ReqStockList_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqStockList] = Response()

        """ Qot_ReqStockSnapshot = 3203  # 获取股票快照 """
        from futuquant.common.pb.Qot_ReqStockSnapshot_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqStockSnapshot] = Response()

        """ Qot_ReqPlateSet = 3204  # 获取板块集合下的板块 """
        from futuquant.common.pb.Qot_ReqPlateSet_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqPlateSet] = Response()

        """ Qot_ReqPlateStock = 3205  # 获取板块下的股票 """
        from futuquant.common.pb.Qot_ReqPlateStock_pb2 import Response
        ProtobufMap.created_protobuf_map[ProtoId.Qot_ReqPlateStock] = Response()

    def __getitem__(self, key):
        return ProtobufMap.created_protobuf_map[key] if key in ProtobufMap.created_protobuf_map else None


pb_map = ProtobufMap()

def binary2str(b, proto_id, proto_fmt_type):
    """
    Transfer binary to string
    :param b: binary content to be transformed to string
    :return: string
    """
    if proto_fmt_type == ProtoFMT.Json:
        return b.decode('utf-8')
    elif proto_fmt_type == ProtoFMT.Protobuf:
        rsp = pb_map[proto_id]
        rsp.ParseFromString(b)
        return MessageToJson(rsp)
    else:
        raise Exception("binary2str: unknown proto format.")


def binary2pb(b, proto_id, proto_fmt_type):
    """
    Transfer binary to pb message
    :param b: binary content to be transformed to pb message
    :return: pb message
    """
    rsp = pb_map[proto_id]
    if rsp is None:
        return None
    if proto_fmt_type == ProtoFMT.Json:
        return json2pb(type(rsp), b.decode('utf-8'))
    elif proto_fmt_type == ProtoFMT.Protobuf:
        rsp.Clear()
        # logger.debug((proto_id))
        rsp.ParseFromString(b)
        return rsp
    else:
        raise Exception("binary2str: unknown proto format.")



def pack_pb_req(pb_req, proto_id, serial_no=0):
    proto_fmt = get_proto_fmt()
    if proto_fmt == ProtoFMT.Json:
        req_json = MessageToJson(pb_req)
        req = _joint_head(proto_id, proto_fmt, len(req_json),
                          req_json.encode(), serial_no)
        return RET_OK, "", req
    elif proto_fmt == ProtoFMT.Protobuf:
        req = _joint_head(proto_id, proto_fmt, pb_req.ByteSize(), pb_req, serial_no)
        return RET_OK, "", req
    else:
        error_str = ERROR_STR_PREFIX + 'unknown protocol format, %d' % proto_fmt
        return RET_ERROR, error_str, None


def _joint_head(proto_id, proto_fmt_type, body_len, str_body, serial_no):
    if proto_fmt_type == ProtoFMT.Protobuf:
        str_body = str_body.SerializeToString()
    fmt = "%s%ds" % (MESSAGE_HEAD_FMT, body_len)

    head_serial_no = serial_no if serial_no else get_unique_id32()
    # print("serial no = {} proto_id = {}".format(head_serial_no, proto_id))
    bin_head = struct.pack(fmt, b'F', b'T', proto_id, proto_fmt_type,
                           API_PROTO_VER, head_serial_no, body_len, 0, 0, 0, 0, 0, 0, 0,
                           0, str_body)
    return bin_head

def parse_head(head_bytes):
    head_dict = {}
    head_dict['head_1'], head_dict['head_2'], head_dict['proto_id'], \
    head_dict['proto_fmt_type'], head_dict['proto_ver'], \
    head_dict['serial_no'], head_dict['body_len'], head_dict['reserved_1'], \
    head_dict['reserved_2'], head_dict['reserved_3'], head_dict['reserved_4'], \
    head_dict['reserved_5'], head_dict['reserved_6'], head_dict['reserved_7'], \
    head_dict['reserved_8'] = struct.unpack(MESSAGE_HEAD_FMT, head_bytes)
    return head_dict