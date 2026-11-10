from .retrieval import retrieve
from .matching import match_profile
from .llm import generate_answer
from .uncertainty import assess_uncertainty, render_uncertainty_markdown
from .effect_extraction import extract_from_papers


def build_report(question, profile, k=8):
    hits = retrieve(question, profile, k=k)
    assessment = assess_uncertainty(hits, profile)
    lines = [
        "# Research briefing",
        "",
        f"**Question:** {question}",
        "",
        "**Profile context:** " + profile_summary(profile),
        "",
        "> Literature-navigation aid only. Not medical advice, diagnosis, treatment guidance, "
        "or a prediction of lifespan. Profile matching is heuristic.",
        "",
        "## Краткий вывод",
        "",
        "Этот прототип нашёл публикации для дальнейшей проверки, но пока не располагает "
        "валидированными структурированными оценками эффектов. Поэтому он не выдаёт "
        "численный объединённый эффект и не превращает релевантность статей в уверенность "
        "в научном утверждении.",
        "",
        render_uncertainty_markdown(assessment),
    ]

    extracted = extract_from_papers([hit["paper"] for hit in hits])
    lines += ["## Численные результаты, найденные в доступном тексте", ""]
    if extracted:
        lines.append("Ниже приведены кандидаты, распознанные регулярными выражениями. Это не проверенные вручную результаты: перед интерпретацией откройте исходную статью и проверьте таблицу/модель.")
        lines.append("")
        for item in extracted:
            ci = (f'95% CI {item["ci95_lower"]:.3g}–{item["ci95_upper"]:.3g}'
                  if item["ci95_lower"] is not None and item["ci95_upper"] is not None else "95% CI не распознан")
            pvalue = item["p_value_text"] or "p-value не распознан"
            lines += [
                f'- **PMID {item["pmid"]} · {item["effect_measure"]} {item["estimate"]:.3g}**; {ci}; {pvalue}; status: `{item["validation_status"]}`',
                f'  - Исход (подсказка по предложению): {item["outcome_hint"] or "не классифицирован"}; follow-up mention: {item["follow_up_source_mention"] or "не извлечён"}; N mention: {item["sample_size_source_mention"] or "не извлечён"}',
                f'  - Тип источника: {item["source_type"]}; ссылка: {item["source_url"] or "URL недоступен"}',
                f'  - Фрагмент: “{item["source_text"]}”',
            ]
            for warning in item["validation_warnings"]:
                lines.append(f'  - **Проверка:** {warning}')
            for error in item["validation_errors"]:
                lines.append(f'  - **Ошибка разбора:** {error}')
        lines.append("")
    else:
        lines += ["В доступных текстах найденных статей распознаваемые HR/RR/OR/IRR с численными оценками не обнаружены. Это не означает, что численных результатов нет в полном тексте.", ""]
    lines += ["Автоматический метаанализ в briefing выключен: совместимость исходов/estimands, популяций, горизонтов наблюдения и независимость когорт нельзя надёжно установить по одному regex-парсеру аннотаций/полного текста. Используйте вкладку Evidence & statistics только после проверки оригинальных источников.", ""]

    answer, fallback_reason = generate_answer(question, profile, hits, assessment)
    if answer:
        lines += ["## Синтез с помощью LLM", "", answer, ""]
    else:
        lines += ["## Статус генерации", "", fallback_reason or "LLM synthesis unavailable.", ""]

    lines += ["## Найденные публикации", ""]
    if not hits:
        lines.append("В локальной базе нет подходящих статей. Сначала запусти сбор PubMed.")
    for i, hit in enumerate(hits, 1):
        p = hit["paper"]
        match = match_profile(p, profile)
        extraction = p.get("extraction_json", {}) or {}
        lines += [
            f"### {i}. {p['title']}",
            f"- Publication date: {p.get('pub_date') or 'not available'}",
            f"- Journal: {p.get('journal') or 'not available'}",
            f"- PMID: {p['pmid']} | [PubMed]({p.get('url')})",
            f"- Retrieval score (TF-IDF): {hit['score']:.3f} *(техническая релевантность, не сила доказательства)*",
            f"- Triage notes: {'; '.join(match['reasons']) or 'No profile match inferred'}",
            f"- Detected study type: {extraction.get('study_type','not classified')} *(эвристика)*",
            "",
            "**Abstract**",
            "",
            (p.get("abstract") or "No abstract available."),
            "",
        ]

    lines += [
        "## Как интерпретировать этот отчёт",
        "",
        "- Число публикаций не равно числу независимых исследований.",
        "- TF-IDF score показывает текстовое сходство с запросом, а не размер эффекта, качество или вероятность истинности.",
        "- Упоминание возраста, пола или заболевания не подтверждает анализ соответствующей подгруппы.",
        "- Без извлечённых и проверенных effect estimates, доверительных интервалов/стандартных ошибок и совместимого исхода метаанализ не выполняется.",
        "- Ассоциация не обязательно означает причинность.",
        "- Прототип не оценивает индивидуальную продолжительность жизни и дополнительные годы жизни.",
    ]
    return "\n".join(lines)


def profile_summary(p):
    return f"age={p.get('age') or 'not set'}, sex={p.get('sex')}, conditions={', '.join(p.get('diseases', [])) or 'none entered'}, interests={', '.join(p.get('interests', [])) or 'not set'}"
