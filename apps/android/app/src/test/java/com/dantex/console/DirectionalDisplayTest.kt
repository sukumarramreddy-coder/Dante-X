package com.dantex.console

import com.dantex.console.data.directionalDisplay
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class DirectionalDisplayTest {
    private fun input(ce: String = "62", pe: String = "38", fresh: Boolean = true, status: String = "PROVISIONAL") =
        JsonParser.parseString("""{"feed_fresh":$fresh,"final":{"action":"NO_EDGE","auto_execution":false},"missing_data":["validated_structural_plan"],"probability_review":{"status":"$status","fresh_evidence":$fresh,"directional":{"ce":$ce,"pe":$pe}}}""")

    @Test fun uncalibratedNoEdgeDisplaysBothPreferencesWithoutAuthorization() {
        val json = input()
        val result = directionalDisplay(json)
        assertEquals("62.0%", result.ce)
        assertEquals("38.0%", result.pe)
        assertTrue(result.label.contains("not profit odds or trade authorization"))
        assertEquals("NO_EDGE", json.asJsonObject.getAsJsonObject("final").get("action").asString)
        assertTrue(result.reasons.contains("validated_structural_plan"))
    }

    @Test fun percentagesAlwaysUseExplicitPercentUnits() {
        assertEquals("1.0%", directionalDisplay(input("1", "99")).ce)
    }

    @Test fun missingMalformedAndExpiredSignalsFailClosed() {
        assertEquals("Unavailable", directionalDisplay(null).ce)
        assertEquals("Unavailable", directionalDisplay(input("80", "80")).ce)
        assertEquals("Unavailable", directionalDisplay(input("\"62\"", "38")).ce)
        assertEquals("Unavailable", directionalDisplay(input(fresh = false)).ce)
        val prior = directionalDisplay(input("50", "50", false, "PRIOR_ONLY"))
        assertEquals("50.0%", prior.ce)
        assertTrue(prior.label.contains("Neutral prior only"))
    }
}
