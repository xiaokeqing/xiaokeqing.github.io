# -*- coding: utf-8 -*-
"""把 lines60.json（中文=页面字幕）扩成双语台词库：每条加 `ja`（送进 TTS 的日文原文）。
  · ja 是"桐莉栖会说的"自然台词（学术/助手语气 + 傲娇），不是机翻；涉及数量的句子一律不复述数字。
  · zh 只用于字幕/审阅，不进 TTS。
输出：lines60-bilingual.json  用法：python make_bilingual.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "lines60.json")
DST = os.path.join(HERE, "lines60-bilingual.json")

JA = {
    "greet_first": "おかえりなさい。画面の数字は全部、実際の読み取り専用インターフェースから来てるの。取れないときは取れないって、はっきり言うから。",
    "greet_back": "また会ったわね。画面のデータは同じ、基準も変わってないわ。",
    "greet_morning": "おはよう。この時間に起きてるなんて、珍しいじゃない。",
    "greet_late_night": "こんな時間まで起きてるの？明日、反省文を代わりに書いてあげる気はないから。",
    "greet_long_absence": "久しぶりね。あなたがいない間も、データの照合は続けてたわ。",
    "greet_quick_return": "また戻ってきたの？マウスだけは頭より速いのね。",
    "greet_first_ever": "はじめまして。牧瀬紅莉栖よ——名前、間違えないで。",
    "greet_cold_open": "来たの？画面は自分で見て。二度は言わないから。",

    "nav_home": "ホームに戻ったわ。私は相変わらず、このモニターの中よ。",
    "nav_monitor": "監視センター。ここにあるのは全部、実際に読み取ったアラート記録よ。",
    "nav_notes": "ノートはこのページ。時系列の逆順で並べてあるわ。",
    "nav_labs": "攻防ラボは検知だけ。実行も処置もしないわ。",
    "nav_about": "このページはプロジェクト自体のこと。データの基準と取捨選択も書いてあるわ。",
    "nav_ai": "質問応答は実際の検索経路を通ってるの。回答はストリーミングじゃないわ。",

    "status_all_clear": "現状はすべて正常よ。アラートが無いなら無いって言うわ。嘘のアラートを作ったりしない。",
    "status_alerts_present": "アラートがあるわ。件数は画面のそれを見て。私、数字を復唱しないの。",
    "status_degraded": "インターフェースが再試行中よ。データが不完全なら、はっきりそう言うわ。中途半端なものは見せない。",
    "status_offline": "上流が切れてるわ。戻ってから結論を言う。",
    "status_late_night": "深夜ね。この時間に起きてるのは、あなたとログだけよ。",
    "status_stale_data": "キャッシュのデータは期限切れよ。さっき起きたことみたいに扱わないで。",
    "status_recovered": "インターフェースは復旧したわ。さっきの空白は覚えてるから、無かったことにはしない。",
    "status_rate_limited": "レート制限よ。少し待って。連打しないで。",
    "status_no_events_today": "今日は新しい事象なしよ。静かなのも情報のうち。",
    "status_first_load": "最初のデータを取り終えたわ。まず基準を揃えさせて。",

    "event_bruteforce": "ブルートフォースの試行よ。ログに連続してるから、発信元ごとにまとめたわ。",
    "event_scan": "ポートスキャンされてるわ。定型的な探索に見えるけど、手は緩めてない。",
    "event_honeypot_hit": "ハニーポットに触られたわ。向こうは安く上がったと思ってるんでしょうね。",
    "event_new_credential": "ハニーポットに新しい認証情報がまた出たわ。誰が試してるのかは記録した。",
    "event_alert_detail": "このアラートには詳細があるわ。原文を開いて。結論だけ見ないで。",
    "event_repeat_offender": "同じ発信元、これで二度目よ。偶然じゃないなら、はっきり書くわ。",
    "event_geo_shift": "発信元の地域が変わったわ。プロキシかもしれない。とりあえず印をつけておく。",
    "event_payload_seen": "ペイロードに怪しい特徴があったわ。印はつけたけど、不確かな部分は不確かなまま書く。",
    "event_defense_no_action": "検知だけよ、実行はしない。私に代わりに手を出させる気？",
    "event_report_written": "事象の読み上げはキューに入ったわ。すぐ読む。データが先、語気は後。",
    "event_quiet_after_storm": "騒ぎは終わったわ。残ってるのは振り返りだけ。",
    "event_unknown_source": "発信元は不明よ。不明なものは不明と書くの。推測しちゃだめ。",

    "tab_return": "戻ったのね。さっきは黙ってたけど、ここで待ってただけよ。",
    "banter_coffee": "画面をぼんやり見てないで。ぼんやりするなら、まずコーヒーを安定させて。",
    "banter_typo": "また打ち間違えたわね。これだけ露骨だと、推測する必要もないわ。",
    "banter_slow_human": "手が思考に追いつかないときは、考えてるってことにしてあげる。",
    "banter_lab_order": "ラボのルール：データが語る、感情は後回し。",
    "banter_no_flattery": "褒めてほしいなんて思わないで。正しいことは正しいって言うだけよ。",
    "banter_time": "時間は早いわね。あなたの進み方はそうでもないけど。",
    "banter_screen_saver": "スクリーンセーバーのほうが、あなたより動いてるわ。",
    "banter_tsundere": "別に待ってたわけじゃないの……たまたま計算が終わってなかっただけ。",
    "banter_note_taking": "思いついたら書き留めなさい。私が覚えてあげるとは思わないで。",
    "banter_wind_down": "今日はここまでにしましょう。残りは明日もそこにあるわ。",
    "banter_mic_check": "あなたの話は聞いてないわ。聞いてるのはデータ。",

    "fallback_no_data": "今回はデータが読めなかったわ。数字を補ったりしない。読めないものは読めないの。",
    "fallback_offline": "リクエストが届かなかったわ。答えを捏造しない。インターフェースが戻るまで待つ。",
    "fallback_throttled": "インターフェースが流量制限中よ。少し待ってから聞いて。",

    "emo_calm_1": "うん、見たわ。別に緊張することなんてない。",
    "emo_calm_2": "ゆっくりでいいわ。データは逃げないから。",
    "emo_serious_1": "これは些事じゃない。まずログを見て、それから結論を出すの。",
    "emo_serious_2": "基準は明確に書くこと。曖昧な結論は認めないわ。",
    "emo_serious_3": "誰かが探ってるわ。証拠は全部残しておいて。",
    "emo_happy_1": "今回はよくできたわ。ぎりぎり合格ってところね。",
    "emo_happy_2": "データが一致したわ。ほら、これが正常な姿よ。",
    "emo_surprised_1": "ちょっと——この変化は予想してなかったわ。",
    "emo_surprised_2": "何？もう一度言って。今、あなたの話は聞いてなかったから。",
}


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    missing = []
    for line in data["lines"]:
        ja = JA.get(line["id"])
        if not ja:
            missing.append(line["id"])
        line["ja"] = ja or ""
        line["zh"] = line["text"]          # 保留原字段，另存一份语义名
    if missing:
        raise SystemExit("缺日文：%s" % missing)
    data["note"] = (data.get("note", "") +
                    " ｜ 双语：`ja` 送进 TTS（桐莉栖的自然日语台词），`zh` 只用于页面字幕与审阅。"
                    "参考音频是日语（kurisu_reference.wav，7.56s 自我介绍），所以目标语言 = 日文。")
    data["ttsField"] = "ja"
    data["subtitleField"] = "zh"
    data["reference"] = {
        "audio": "./assets/audio/reference/kurisu_reference.wav",
        "language": "日文",
        "transcript": "そういえば,正式に自己紹介していませんでしたね……牧瀬紅莉栖です.改めてまして,よろしく",
        "transcriptSource": "config/catalog/voice/voice_reference_profile.json 的 default（catalog 默认值）",
        "seconds": 7.56,
    }
    json.dump(data, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("→", DST, "| 条数", len(data["lines"]), "| 全部有日文:", not missing)


if __name__ == "__main__":
    main()
