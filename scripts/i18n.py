"""UI translations and locale routing.

Only site chrome is translated. Repository descriptions, topics and languages
come from the GitHub API as arbitrary user text — translating them would need a
machine-translation service, which this project deliberately does not have, and
machine-translated technical descriptions are usually worse than the original.

English is served at the root; other locales live under /<code>/. Every page
declares hreflang alternates for all locales plus x-default, so search engines
treat them as translations of one another rather than duplicate content.
"""

# Order matters: it is the order of the language switcher, and the first entry
# is the default served at the root.
LOCALES = ("en", "vi", "zh")

LOCALE_NAMES = {"en": "English", "vi": "Tiếng Việt", "zh": "中文"}

# BCP 47 tags for the lang attribute and hreflang. "zh-Hans" rather than bare
# "zh": the copy is Simplified, and being explicit avoids Traditional readers
# being served the wrong variant.
LOCALE_TAGS = {"en": "en", "vi": "vi", "zh": "zh-Hans"}

STRINGS = {
    "en": {
        "skip": "Skip to content",
        "nav_day": "Today",
        "nav_week": "Week",
        "nav_month": "Month",
        "nav_topics": "Topics",
        "nav_languages": "Languages",
        "nav_methodology": "Methodology",
        "nav_label": "Primary",
        "lang_label": "Language",

        "home_title": "gitpulse — GitHub repositories, ranked by momentum",
        "home_h1": "GitHub repositories, ranked by momentum",
        "home_desc": "Daily star snapshots across GitHub, turned into real 1d/7d/30d "
                     "growth rates. Only substantive repositories get a page.",
        "home_lede": "{tracked} repositories tracked with daily star snapshots. "
                     "{published} substantive enough to have a page.",
        "search_label": "Filter all tracked repositories",
        "search_placeholder": "Search by name or description...",
        "search_none": "No repositories match that search.",
        "rising": "Rising this week",

        "lede_day": "Ranked by star growth over the last day.",
        "lede_week": "Ranked by star growth over the last 7 days.",
        "lede_month": "Ranked by star growth over the last 30 days.",
        "desc_day": "GitHub repositories gaining stars fastest in the last day.",
        "desc_week": "GitHub repositories gaining stars fastest in the last 7 days.",
        "desc_month": "GitHub repositories gaining stars fastest in the last 30 days.",
        "lede_stars": "Ordered by star count.",
        "fallback_title": "Not enough movement to rank this window yet",
        "fallback_body": "No tracked repository gained at least {delta} stars in this window, so this list is ordered by star count rather than by growth.",
        "window_day": "Today",
        "window_week": "This week",
        "window_month": "This month",

        "notice_title": "Momentum data is still accumulating",
        "notice_body": "GitHub only exposes a repository's current star count, so growth "
                       "rates have to be built up one daily snapshot at a time and cannot "
                       "be backfilled. {have} of the 7 snapshots needed for a weekly figure "
                       "have been collected. Until then, listings are ordered by star count.",
        "no_history": "no history yet",
        "stars": "stars",
        "forks": "forks",
        "pushed": "pushed",

        "repo_momentum": "Star momentum",
        "repo_topics": "Topics",
        "repo_github": "View on GitHub",
        "repo_no_chart": "Not enough daily snapshots yet for a chart — {have} collected, "
                         "{need} needed.",
        "repo_none": "none",

        "topics_h1": "Topics",
        "languages_h1": "Languages",
        "facet_lede": "{count} {kind} with at least {min} published repositories.",
        "facet_members": "{count} published repositories.",
        "col_repositories": "Repositories",
        "facet_desc": "Browse tracked GitHub repositories by {kind}.",
        "facet_page_desc": "Tracked GitHub repositories for {value}.",
        "facet_page_title": "{value} repositories",

        "methodology_title": "Methodology — gitpulse",
        "methodology_desc": "How repositories are tracked, ranked and published.",
        "methodology_h1": "Methodology",
        "methodology_lede": "Every figure comes from GitHub's public API. Nothing is "
                            "invented, and there are no editorial ratings.",
        "m_tracked_h": "What gets tracked",
        "m_tracked_p": "Repositories at or above <strong>{gate}</strong> stars get a page. "
                       "Repositories from <strong>{floor}</strong> stars upward are tracked "
                       "in the dataset without a page, so a smaller project that starts "
                       "accelerating can be promoted. Currently {tracked} tracked, "
                       "{published} published.",
        "m_velocity_h": "How momentum is computed",
        "m_velocity_p1": "Star counts are snapshotted once a day. GitHub exposes only the "
                         "current count, so history has to be accumulated and cannot be "
                         "backfilled.",
        "m_velocity_p2": "A window compares the current count against the most recent "
                         "snapshot on or before that many days ago. If the nearest available "
                         "snapshot is more than {tolerance} days staler than the target, no "
                         "figure is published for that window rather than a mislabelled one. "
                         "A repository without enough history shows no momentum at all, "
                         "never zero.",
        "m_rank_h": "Ranking",
        "m_rank_p": "Trending pages rank by percentage growth, but only for repositories "
                    "that also gained at least <strong>{delta}</strong> stars in the window. "
                    "Percentage alone favours tiny absolute moves on small repositories.",
        "m_gate_h": "Publishing thresholds",
        "m_gate_p": "A repository gets a page when it is not archived, has a description, "
                    "was pushed within {days} days, and either passes the star threshold "
                    "above or gained at least {pct}% over 7 days. Topic and language pages "
                    "need at least {members} members.",
        "m_stat_p": "{count} published repositories currently have enough history for a "
                    "7-day figure.",

        "footer_data": "Repository data from the GitHub API. Updated {date}.",
        "footer_how": "How ranking works",
        "footer_source": "Source",
    },
    "vi": {
        "skip": "Tới nội dung chính",
        "nav_day": "Hôm nay",
        "nav_week": "Tuần",
        "nav_month": "Tháng",
        "nav_topics": "Chủ đề",
        "nav_languages": "Ngôn ngữ",
        "nav_methodology": "Phương pháp",
        "nav_label": "Chính",
        "lang_label": "Ngôn ngữ",

        "home_title": "gitpulse — Kho GitHub xếp theo đà tăng trưởng",
        "home_h1": "Kho GitHub xếp theo đà tăng trưởng",
        "home_desc": "Chụp số sao GitHub mỗi ngày, quy ra tốc độ tăng thật theo 1/7/30 ngày. "
                     "Chỉ kho có nội dung đáng kể mới có trang riêng.",
        "home_lede": "Đang theo dõi {tracked} kho với ảnh chụp số sao hằng ngày. "
                     "{published} kho đủ điều kiện có trang riêng.",
        "search_label": "Lọc toàn bộ kho đang theo dõi",
        "search_placeholder": "Tìm theo tên hoặc mô tả...",
        "search_none": "Không có kho nào khớp.",
        "rising": "Tăng mạnh tuần này",

        "lede_day": "Xếp theo mức tăng sao trong 1 ngày qua.",
        "lede_week": "Xếp theo mức tăng sao trong 7 ngày qua.",
        "lede_month": "Xếp theo mức tăng sao trong 30 ngày qua.",
        "desc_day": "Kho GitHub tăng sao nhanh nhất trong 1 ngày qua.",
        "desc_week": "Kho GitHub tăng sao nhanh nhất trong 7 ngày qua.",
        "desc_month": "Kho GitHub tăng sao nhanh nhất trong 30 ngày qua.",
        "lede_stars": "Xếp theo số sao.",
        "fallback_title": "Chưa đủ biến động để xếp hạng khung này",
        "fallback_body": "Chưa kho nào tăng ít nhất {delta} sao trong khung này, nên danh sách xếp theo số sao thay vì theo mức tăng.",
        "window_day": "Hôm nay",
        "window_week": "Tuần này",
        "window_month": "Tháng này",

        "notice_title": "Dữ liệu đà tăng đang được tích lũy",
        "notice_body": "GitHub chỉ cho biết số sao hiện tại, nên tốc độ tăng phải tích lũy "
                       "từng ngày một và không thể bù ngược. Đã thu được {have}/7 ảnh chụp "
                       "cần thiết cho chỉ số tuần. Trong lúc chờ, danh sách xếp theo số sao.",
        "no_history": "chưa có lịch sử",
        "stars": "sao",
        "forks": "fork",
        "pushed": "cập nhật",

        "repo_momentum": "Đà tăng sao",
        "repo_topics": "Chủ đề",
        "repo_github": "Xem trên GitHub",
        "repo_no_chart": "Chưa đủ ảnh chụp hằng ngày để vẽ biểu đồ — có {have}, cần {need}.",
        "repo_none": "không có",

        "topics_h1": "Chủ đề",
        "languages_h1": "Ngôn ngữ",
        "facet_lede": "{count} {kind} có ít nhất {min} kho được công bố.",
        "facet_members": "{count} kho được công bố.",
        "col_repositories": "Số kho",
        "facet_desc": "Duyệt kho GitHub đang theo dõi theo {kind}.",
        "facet_page_desc": "Kho GitHub đang theo dõi thuộc {value}.",
        "facet_page_title": "Kho {value}",

        "methodology_title": "Phương pháp — gitpulse",
        "methodology_desc": "Cách kho được theo dõi, xếp hạng và công bố.",
        "methodology_h1": "Phương pháp",
        "methodology_lede": "Mọi con số đều lấy từ API công khai của GitHub. Không bịa số, "
                            "không có điểm đánh giá chủ quan.",
        "m_tracked_h": "Những gì được theo dõi",
        "m_tracked_p": "Kho từ <strong>{gate}</strong> sao trở lên có trang riêng. Kho từ "
                       "<strong>{floor}</strong> sao trở lên vẫn được theo dõi trong dữ liệu "
                       "dù chưa có trang, nhờ đó một dự án nhỏ bắt đầu bứt tốc có thể được "
                       "đưa lên. Hiện theo dõi {tracked} kho, công bố {published} kho.",
        "m_velocity_h": "Cách tính đà tăng",
        "m_velocity_p1": "Số sao được chụp lại mỗi ngày một lần. GitHub chỉ cho biết số hiện "
                         "tại, nên lịch sử phải tích lũy dần và không thể bù ngược.",
        "m_velocity_p2": "Mỗi khung thời gian so số hiện tại với ảnh chụp gần nhất tại hoặc "
                         "trước mốc đó. Nếu ảnh chụp gần nhất cũ hơn mốc quá {tolerance} "
                         "ngày, khung đó không công bố số thay vì công bố một con số gán sai "
                         "nhãn. Kho chưa đủ lịch sử thì không hiện đà tăng, chứ không hiện 0.",
        "m_rank_h": "Xếp hạng",
        "m_rank_p": "Trang xu hướng xếp theo phần trăm tăng, nhưng chỉ với kho đồng thời tăng "
                    "ít nhất <strong>{delta}</strong> sao trong khung đó. Chỉ dựa vào phần "
                    "trăm sẽ thiên vị các dao động nhỏ ở kho nhỏ.",
        "m_gate_h": "Ngưỡng công bố",
        "m_gate_p": "Một kho có trang riêng khi chưa lưu trữ, có mô tả, được push trong "
                    "{days} ngày, và hoặc vượt ngưỡng sao ở trên hoặc tăng ít nhất {pct}% "
                    "trong 7 ngày. Trang chủ đề và ngôn ngữ cần ít nhất {members} thành viên.",
        "m_stat_p": "Hiện có {count} kho đã công bố đủ lịch sử cho chỉ số 7 ngày.",

        "footer_data": "Dữ liệu kho lấy từ API GitHub. Cập nhật {date}.",
        "footer_how": "Cách xếp hạng",
        "footer_source": "Mã nguồn",
    },
    "zh": {
        "skip": "跳至正文",
        "nav_day": "今日",
        "nav_week": "本周",
        "nav_month": "本月",
        "nav_topics": "主题",
        "nav_languages": "语言",
        "nav_methodology": "方法说明",
        "nav_label": "主导航",
        "lang_label": "语言",

        "home_title": "gitpulse — 按增长动能排序的 GitHub 仓库",
        "home_h1": "按增长动能排序的 GitHub 仓库",
        "home_desc": "每日采集 GitHub 星标快照，换算成真实的 1/7/30 天增长率。只有内容充实的仓库才有独立页面。",
        "home_lede": "已跟踪 {tracked} 个仓库并每日采集星标快照，其中 {published} 个达到独立页面标准。",
        "search_label": "筛选所有已跟踪的仓库",
        "search_placeholder": "按名称或描述搜索…",
        "search_none": "没有匹配的仓库。",
        "rising": "本周上升",

        "lede_day": "按过去 1 天的星标增长排序。",
        "lede_week": "按过去 7 天的星标增长排序。",
        "lede_month": "按过去 30 天的星标增长排序。",
        "desc_day": "过去 1 天星标增长最快的 GitHub 仓库。",
        "desc_week": "过去 7 天星标增长最快的 GitHub 仓库。",
        "desc_month": "过去 30 天星标增长最快的 GitHub 仓库。",
        "lede_stars": "按星标数排序。",
        "fallback_title": "该时间窗口的变动尚不足以排名",
        "fallback_body": "在该窗口内没有仓库增加至少 {delta} 颗星标，因此此列表按星标数排序，而非按增长排序。",
        "window_day": "今日",
        "window_week": "本周",
        "window_month": "本月",

        "notice_title": "增长数据仍在积累中",
        "notice_body": "GitHub 只提供仓库当前的星标数，因此增长率必须逐日累积，无法回溯补齐。"
                       "周度指标所需的 7 份快照目前已采集 {have} 份。在此之前，列表按星标数排序。",
        "no_history": "暂无历史",
        "stars": "星标",
        "forks": "复刻",
        "pushed": "推送于",

        "repo_momentum": "星标动能",
        "repo_topics": "主题",
        "repo_github": "在 GitHub 上查看",
        "repo_no_chart": "每日快照尚不足以绘制图表 — 已有 {have} 份，需要 {need} 份。",
        "repo_none": "无",

        "topics_h1": "主题",
        "languages_h1": "语言",
        "facet_lede": "{count} 个{kind}至少包含 {min} 个已发布仓库。",
        "facet_members": "{count} 个已发布仓库。",
        "col_repositories": "仓库数",
        "facet_desc": "按{kind}浏览已跟踪的 GitHub 仓库。",
        "facet_page_desc": "属于 {value} 的已跟踪 GitHub 仓库。",
        "facet_page_title": "{value} 仓库",

        "methodology_title": "方法说明 — gitpulse",
        "methodology_desc": "仓库如何被跟踪、排序与发布。",
        "methodology_h1": "方法说明",
        "methodology_lede": "所有数字均来自 GitHub 公开 API。没有虚构数据，也没有主观评分。",
        "m_tracked_h": "跟踪范围",
        "m_tracked_p": "星标数达到 <strong>{gate}</strong> 及以上的仓库拥有独立页面。"
                       "星标数从 <strong>{floor}</strong> 起的仓库虽无页面但仍进入数据集，"
                       "因此开始加速的小项目可以被提升上来。当前已跟踪 {tracked} 个，"
                       "已发布 {published} 个。",
        "m_velocity_h": "动能的计算方式",
        "m_velocity_p1": "星标数每天采集一次快照。GitHub 只暴露当前数值，因此历史必须逐步累积，无法回溯补齐。",
        "m_velocity_p2": "每个时间窗口将当前数值与该天数之前（含当天）最近的一份快照比较。"
                         "若最近的快照比目标日期还早 {tolerance} 天以上，该窗口将不发布数字，"
                         "而不是给出一个标注错误的数字。历史不足的仓库完全不显示动能，而非显示 0。",
        "m_rank_h": "排序规则",
        "m_rank_p": "趋势页按百分比增长排序，但仅限在该窗口内同时增加了至少 <strong>{delta}</strong> "
                    "颗星标的仓库。仅看百分比会偏袒小仓库的微小绝对变动。",
        "m_gate_h": "发布门槛",
        "m_gate_p": "仓库需未归档、有描述、在 {days} 天内有过推送，并且满足上述星标门槛"
                    "或在 7 天内增长至少 {pct}%，才会获得页面。主题页和语言页至少需要 "
                    "{members} 个成员。",
        "m_stat_p": "目前有 {count} 个已发布仓库积累了足够的 7 天历史数据。",

        "footer_data": "仓库数据来自 GitHub API。更新于 {date}。",
        "footer_how": "排序说明",
        "footer_source": "源码",
    },
}


def t(locale, key, **kwargs):
    """Look up a string, falling back to English if a key is untranslated."""
    value = STRINGS.get(locale, {}).get(key) or STRINGS["en"][key]
    return value.format(**kwargs) if kwargs else value


def prefix(locale):
    """Path segment for a locale. English is served at the root."""
    return "" if locale == LOCALES[0] else f"/{locale}"
