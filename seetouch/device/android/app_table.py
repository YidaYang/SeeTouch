"""高频 app 的中文名 -> Android package 静态表。

只覆盖国内常用应用(L1 快速路径)。未命中时由 app_launcher 走 L2-L4。

PACKAGE_ALIASES 处理"模型输出海外/旧版包名,但设备上装的是国内/新版"的情况。
"""

from __future__ import annotations

# 静态映射:中文名 -> Android package
# 包名以应用商店主流版本为准,部分应用国内/海外版会有差异
APP_TABLE: dict[str, str] = {
    # 视频 / 直播
    "哔哩哔哩": "tv.danmaku.bili",
    "B站": "tv.danmaku.bili",
    "抖音": "com.ss.android.ugc.aweme",
    "快手": "com.smile.gifmaker",
    "腾讯视频": "com.tencent.qqlive",
    "爱奇艺": "com.qiyi.video",
    "优酷": "com.youku.phone",
    "芒果TV": "com.hunantv.imgo.activity",
    "西瓜视频": "com.ss.android.article.video",
    # 社交 / 沟通
    "微信": "com.tencent.mm",
    "QQ": "com.tencent.mobileqq",
    "小红书": "com.xingin.xhs",
    "微博": "com.sina.weibo",
    "知乎": "com.zhihu.android",
    # 电商
    "淘宝": "com.taobao.taobao",
    "京东": "com.jingdong.app.mall",
    "拼多多": "com.xunmeng.pinduoduo",
    "天猫": "com.tmall.wireless",
    # 生活 / 出行
    "美团": "com.sankuai.meituan",
    "美团外卖": "com.sankuai.meituan",
    "饿了么": "me.ele",
    "高德地图": "com.autonavi.minimap",
    "百度地图": "com.baidu.BaiduMap",
    "滴滴出行": "com.sdu.didi.psnger",
    "去哪儿旅行": "com.Qunar",
    "去哪旅行": "com.Qunar",
    "携程旅行": "ctrip.android.view",
    "飞猪旅行": "com.taobao.trip",
    # 工具 / 支付
    "支付宝": "com.eg.android.AlipayGphone",
    # 音乐 / 音频
    "网易云音乐": "com.netease.cloudmusic",
    "QQ音乐": "com.tencent.qqmusic",
    "喜马拉雅": "com.ximalaya.ting.android",
    # 浏览器 / 搜索
    "百度": "com.baidu.searchbox",
    "夸克": "com.quark.browser",
}


# 海外/旧版 package -> 国内常用替代。模型若给出 key,系统先看看 value 是否装在设备上。
PACKAGE_ALIASES: dict[str, str] = {
    "com.zhiliaoapp.musically": "com.ss.android.ugc.aweme",  # TikTok -> 抖音
    "com.zhiliaoapp.musically.go": "com.ss.android.ugc.aweme",
    "com.kuaishou.tiny": "com.smile.gifmaker",  # 快手极速版变体
    "com.alibaba.android.rimet": "com.alibaba.android.rimet",  # 钉钉:占位,后续可补
}


def normalize_name(name: str) -> str:
    """标准化 app 名:trim + 简单别名展开。"""
    name = (name or "").strip()
    aliases = {
        "b站": "哔哩哔哩",
        "bilibili": "哔哩哔哩",
        "美团外卖": "美团",
        "去哪旅行": "去哪儿旅行",
    }
    return aliases.get(name.lower(), name)


def lookup(name: str) -> str | None:
    """查表:中文名(或英文别名)-> package。未命中返回 None。"""
    if not name:
        return None
    n = normalize_name(name)
    if n in APP_TABLE:
        return APP_TABLE[n]
    # 大小写不敏感再扫一次
    lower = n.lower()
    for key, pkg in APP_TABLE.items():
        if key.lower() == lower:
            return pkg
    return None


def alias_for_package(package: str) -> str | None:
    """若给定 package 在 PACKAGE_ALIASES 里,返回国内替代 package。否则 None。"""
    return PACKAGE_ALIASES.get((package or "").strip()) or None
