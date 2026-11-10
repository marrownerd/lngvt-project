"""Transparent, rule-based uncertainty diagnostics for literature briefings.

This module deliberately avoids producing a single pseudo-precise confidence score.
It reports observable limitations of the retrieved corpus and what would reduce them.
"""
from collections import Counter


def _paper_type(paper):
    extraction = paper.get("extraction_json") or paper.get("extraction") or {}
    return extraction.get("study_type", "not_classified") or "not_classified"


def assess_uncertainty(hits, profile=None):
    profile = profile or {}
    papers = [h.get("paper", {}) for h in hits]
    n = len(papers)
    with_abstract = sum(bool((p.get("abstract") or "").strip()) for p in papers)
    classified = sum(_paper_type(p) != "not_classified" for p in papers)
    types = Counter(_paper_type(p) for p in papers)
    pmids = [str(p.get("pmid")) for p in papers if p.get("pmid")]
    duplicate_ids = len(pmids) - len(set(pmids))

    limitations = []
    strengths = []
    actions = []

    if n == 0:
        limitations.append({
            "area": "Evidence coverage",
            "level": "critical",
            "reason": "В локальной библиотеке не найдено публикаций по запросу.",
            "implication": "Нельзя делать вывод об отсутствии эффекта: это означает только отсутствие найденных записей.",
        })
        actions.append("Расширить поисковый запрос и временной диапазон; проверить PubMed и другие источники.")
    else:
        strengths.append(f"В локальной выдаче найдено {n} публикаций. Это число записей, а не число независимых исследований.")
        if with_abstract < n:
            limitations.append({
                "area": "Доступность содержания",
                "level": "high",
                "reason": f"Аннотация доступна только у {with_abstract} из {n} публикаций.",
                "implication": "Для записей без аннотаций невозможно содержательно оценить методы и результаты.",
            })
            actions.append("Получить доступные аннотации или разрешённые полные тексты и повторить извлечение.")
        if classified < n:
            limitations.append({
                "area": "Дизайн исследования",
                "level": "high",
                "reason": f"Тип исследования эвристически определён только для {classified} из {n} публикаций.",
                "implication": "Нельзя надёжно взвесить доказательства по дизайну исследования.",
            })
            actions.append("Проверить дизайн исследования по полному тексту и зарегистрированному протоколу.")
        if duplicate_ids:
            limitations.append({
                "area": "Дублирование",
                "level": "high",
                "reason": f"В выдаче обнаружено {duplicate_ids} повторяющихся PMID.",
                "implication": "Повторный учёт одной записи может искусственно увеличить видимый объём доказательств.",
            })
            actions.append("Проверить дедупликацию по PMID, DOI и идентификаторам исходных когорт/испытаний.")

    # Population matching is only mention-based in this prototype.
    requested_sex = profile.get("sex")
    sex_known = sum(bool((p.get("inferred_sexes") or [])) for p in papers)
    if requested_sex in ("female", "male") and n:
        limitations.append({
            "area": "Переносимость по полу",
            "level": "high",
            "reason": f"Пол упоминается в извлечённых метаданных у {sex_known} из {n} публикаций; это поиск упоминаний, а не подтверждение анализа подгруппы.",
            "implication": "Нельзя заключить, что оценка эффекта отдельно рассчитана для выбранного пола.",
        })
        actions.append("Проверить критерии включения, распределение участников и subgroup estimates в полных текстах.")

    age = profile.get("age")
    age_known = sum(bool((p.get("inferred_age_groups") or [])) for p in papers)
    if age is not None and n:
        limitations.append({
            "area": "Переносимость по возрасту",
            "level": "high",
            "reason": f"Возрастная группа упоминается у {age_known} из {n} публикаций; точный возраст и отдельные возрастные эффекты не подтверждены.",
            "implication": "Нельзя считать, что средний эффект применим к конкретному возрасту пользователя.",
        })
        actions.append("Извлечь возрастные распределения и результаты заранее заданных возрастных подгрупп.")

    disease_count = len(profile.get("diseases", []) or [])
    if disease_count and n:
        disease_mentions = sum(bool(set(x.lower() for x in (p.get("inferred_diseases") or [])) &
                                    set(x.lower() for x in profile.get("diseases", []))) for p in papers)
        limitations.append({
            "area": "Переносимость по заболеваниям",
            "level": "high",
            "reason": f"Совпадающие термины заболеваний найдены у {disease_mentions} из {n} публикаций; упоминание не доказывает включение пациентов с этим заболеванием или анализ соответствующей подгруппы.",
            "implication": "Нельзя утверждать, что результат применим к людям с указанным заболеванием.",
        })
        actions.append("Проверить критерии включения/исключения, коморбидность и отдельные оценки эффекта для нужной группы.")

    limitations.extend([
        {
            "area": "Размер и направление эффекта",
            "level": "critical" if n else "high",
            "reason": "Добавлено предварительное regex-извлечение HR/RR/OR/IRR из аннотаций и доступного open-access полного текста с проверкой CI/p-value, однако оно не валидировано на размеченном медицинском benchmark и не подтверждает корректность модели исследования.",
            "implication": "Автоматическое объединение найденных статей остаётся отключённым. Для статистического синтеза нужны проверка первоисточников, совместимость estimand/outcome/population/follow-up/design и независимость когорт; TF-IDF score не является размером эффекта или вероятностью истинности.",
        },
        {
            "area": "Причинность и смешение факторов",
            "level": "high",
            "reason": "По одним заголовкам и аннотациям нельзя надёжно проверить confounding, selection bias, missing data и другие источники систематической ошибки.",
            "implication": "Наблюдаемая ассоциация не должна пересказываться как доказанный причинный эффект.",
        },
        {
            "area": "Полнота поиска и публикационное смещение",
            "level": "high",
            "reason": "Отчёт строится по ограниченной локальной коллекции и top-K результатам TF-IDF, а не по зарегистрированному систематическому протоколу поиска.",
            "implication": "Отсутствие противоречащих статей в выдаче не означает отсутствия противоречащих данных в литературе.",
        },
        {
            "area": "Независимость исследований",
            "level": "high",
            "reason": "MVP не устанавливает надёжно, используют ли разные публикации одну и ту же когорту или испытание.",
            "implication": "Считать каждую публикацию независимым наблюдением и объединять их статистически пока нельзя.",
        },
    ])
    actions.extend([
        "Проверить каждую извлечённую численную оценку в оригинальной таблице/модели статьи; улучшить парсер по benchmark вручную размеченных аннотаций и полных текстов.",
        "Сопоставить исследования по одному estimand, исходу, шкале эффекта и временному горизонту до метаанализа.",
        "Оценить риск систематической ошибки подходящим инструментом (например, RoB 2 или ROBINS-I).",
        "Проверить перекрытие когорт, протоколы, поправки на confounding и публикационные смещения.",
        "Провести benchmark на вручную размеченных статьях и оценить precision/recall извлечения.",
    ])

    # De-duplicate action text while preserving order.
    actions = list(dict.fromkeys(actions))
    return {
        "retrieved_records": n,
        "abstracts_available": with_abstract,
        "study_types_classified": classified,
        "study_type_counts": dict(types),
        "strengths": strengths,
        "limitations": limitations,
        "uncertainty_reduction_actions": actions,
        "statistical_pooling_ready": False,
        "statistical_readiness_reason": (
            "Нет проверенных, структурированных и сопоставимых оценок эффекта с дисперсиями, "
            "а также проверки независимости исследований. Поэтому численное объединение отключено."
        ),
        "interpretation": "Это диагностика ограничений доступной выдачи, а не формальная оценка certainty of evidence (например, GRADE).",
    }


def render_uncertainty_markdown(assessment):
    lines = ["## Что мы знаем и в чём сомневаемся", ""]
    lines.append("### Что можно сказать о найденной выборке")
    if assessment["strengths"]:
        lines.extend(f"- {x}" for x in assessment["strengths"])
    else:
        lines.append("- В текущей локальной выдаче нет публикаций.")
    lines += ["", "### Почему выводы пока ненадёжны", ""]
    for item in assessment["limitations"]:
        lines += [
            f"#### {item['area']} — уровень ограничения: **{item['level']}**",
            f"- **Причина сомнения:** {item['reason']}",
            f"- **Что это означает:** {item['implication']}",
            "",
        ]
    lines += ["### Что уменьшит неопределённость", ""]
    lines.extend(f"- {x}" for x in assessment["uncertainty_reduction_actions"])
    lines += [
        "",
        "### Статистическая готовность",
        "",
        f"**Метаанализ / Bayesian pooling:** {'доступен' if assessment['statistical_pooling_ready'] else 'не выполняется'}.",
        assessment["statistical_readiness_reason"],
        "",
        f"> {assessment['interpretation']}",
        "",
    ]
    return "\n".join(lines)
