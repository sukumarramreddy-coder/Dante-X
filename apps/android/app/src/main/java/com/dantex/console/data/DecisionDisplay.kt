package com.dantex.console.data

import com.google.gson.JsonElement
import java.util.Locale

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

fun directionalDisplay(decision: JsonElement?): DirectionalDisplay {
    val root = decision.objectOrNull()
    val review = root?.obj("probability_review")
    val directional = review?.obj("directional")
    val ce = directional?.get("ce").percentage()
    val pe = directional?.get("pe").percentage()
    val fresh = review?.bool("fresh_evidence") == true && root?.bool("feed_fresh") == true
    val prior = review?.string("status") == "PRIOR_ONLY" && ce == 50.0 && pe == 50.0
    val valid = ce != null && pe != null && kotlin.math.abs(ce + pe - 100) < .01 && (fresh || prior)
    val reasons = (root?.get("missing_data").strings() +
        review?.get("blocked_sources").strings() + review?.get("data_reasons").strings() +
        review?.get("missing_families").strings()).distinct()
    return DirectionalDisplay(
        if (valid) String.format(Locale.US, "%.1f%%", ce) else "Unavailable",
        if (valid) String.format(Locale.US, "%.1f%%", pe) else "Unavailable",
        when {
            valid && fresh && !prior -> "Provisional heuristic. Uncalibrated; not profit odds or trade authorization."
            valid -> "Neutral prior only. Uncalibrated; not a current directional signal or profit odds."
            else -> "Directional evidence unavailable. No percentage is substituted."
        },
        if (fresh) "Fresh evidence" else "Stale, missing or pending evidence",
        reasons
    )
}
