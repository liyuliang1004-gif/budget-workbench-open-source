def normalize_text(value: str | None) -> str:
    return str(value or "").strip().lower()


EXPENSE_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("营销费用", ("dou", "doU".lower(), "福袋", "抖币", "千川", "平台扣点", "佣金", "达播", "达人", "推广", "广告", "直通车", "京挑客", "品销宝", "超级推荐", "投流", "维护费", "赠品", "样品")),
    ("人员费用", ("工资", "社保", "社会保险", "公积金", "人员", "绩效", "奖金", "福利")),
    ("运输装卸费", ("快递", "物流", "运费", "打包", "包材", "仓储", "装卸", "配送")),
    ("税金费用", ("税金", "税费", "税")),
    ("资金占压费用", ("资金", "占压", "利息")),
    ("租赁费", ("租赁", "租金", "房租")),
    ("差旅费", ("差旅", "住宿", "机票", "高铁")),
    ("客诉费", ("客诉", "赔付", "售后")),
    ("评价维护", ("评价", "刷评", "买家秀")),
    ("管理费", ("办公", "软件", "宽带", "通讯", "水电", "维修", "低值", "招待", "会务", "检测", "折旧", "交通", "邮寄", "制版", "服务费", "店铺费用", "账扣", "线下")),
]


def classify_actual_expense_category(reason: str | None, fallback: str | None = None) -> str:
    text = normalize_text(reason)
    for category, keywords in EXPENSE_CATEGORY_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            return category
    fallback_text = str(fallback or "").strip()
    return fallback_text if fallback_text and fallback_text != "实际费用" else "未分类实际费用"
