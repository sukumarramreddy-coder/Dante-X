package com.dantex.console.data

import com.google.gson.JsonElement
import java.util.Locale
import java.time.Instant
import java.time.OffsetDateTime

data class DirectionalDisplay(
    val ce: String,
    val pe: String,
    val label: String,
    val quality: String,
    val reasons: List<String>
)

fun JsonElement?.strings(): List<String> =
    if (this != null && isJsonArray) asJsonArray.mapNotNull {
        if (it.isJsonPrimitive && it.asJsonPrimitive.isString) it.asString else null
    } else emptyList()

private fun JsonElement?.percentage(): Double? =
    if (this != null && isJsonPrimitive && asJsonPrimitive.isNumber)
        runCatching { asDouble }.getOrNull()?.takeIf { it.isFinite() && it in 0.0..100.0 }
    else null

fun directionalDisplay(decision: JsonElement?, symbol: String? = null, now: Instant = Instant.now()): DirectionalDisplay {
    val root = decision.objectOrNull()
    val review = if (symbol == null) root?.obj("probability_review")
        else root?.obj("index_probability_reviews")?.obj(symbol)
    val correctScope = symbol == null || (review?.string("scope") == symbol && review.string("unit") == "percent")
    val current = if (symbol == null) true else runCatching {
        val at = OffsetDateTime.parse(review?.string("timestamp")).toInstant()
        java.time.Duration.between(at, now).seconds in -5..60
    }.getOrDefault(false)
    val directional = review?.obj("directional")
    val ce = directional?.get("ce").percentage()
    val pe = directional?.get("pe").percentage()
    val fresh = review?.bool("fresh_evidence") == true && current &&
        (if (symbol == null) root?.bool("feed_fresh") == true else root?.bool("restored_from_audit") != true)
    val prior = review?.string("status") == "PRIOR_ONLY" && ce == 50.0 && pe == 50.0
    val valid = correctScope && ce != null && pe != null && kotlin.math.abs(ce + pe - 100) < .01 && (fresh || prior)
    val reasons = (root?.get("missing_data").strings().filter { symbol == null || it.startsWith("$symbol.") || !it.contains(".") } +
        review?.get("blocked_sources").strings() + review?.get("data_reasons").strings() +
        review?.get("missing_families").strings()).distinct()
    return DirectionalDisplay(
        if (valid) String.format(Locale.US, "%.1f%%", ce) else "Unavailable",
        if (valid) String.format(Locale.US, "%.1f%%", pe) else "Unavailable",
        when {
            valid && fresh && !prior -> "Provisional heuristic. Uncalibrated; not profit odds or trade authorization."
            valid -> "Neutral prior only. Uncalibrated; not a current directional signal or profit odds."
            else -> if (symbol != null && review == null) "Update the engine to show separate index probabilities." else "Directional evidence unavailable. No percentage is substituted."
        },
        if (fresh) "Fresh evidence" else "Stale, missing or pending evidence",
        reasons
    )
}
