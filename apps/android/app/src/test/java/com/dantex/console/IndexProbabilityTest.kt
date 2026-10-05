package com.dantex.console

import com.dantex.console.data.directionalDisplay
import com.google.gson.JsonParser
import java.time.Instant
import org.junit.Assert.*
import org.junit.Test

class IndexProbabilityTest {
    private val now = Instant.parse("2026-10-05T05:00:00Z")
    private fun input() = JsonParser.parseString("""{
        "feed_fresh":false,"final":{"action":"NO_EDGE","auto_execution":false},
        "missing_data":["NIFTY.vwap","BANKNIFTY.verified_greeks"],
        "index_probability_reviews":{
          "NIFTY":{"scope":"NIFTY","unit":"percent","status":"PROVISIONAL","timestamp":"2026-10-05T10:30:00+05:30","fresh_evidence":true,"directional":{"ce":65,"pe":35}},
          "BANKNIFTY":{"scope":"BANKNIFTY","unit":"percent","status":"PROVISIONAL","timestamp":"2026-10-05T10:30:00+05:30","fresh_evidence":true,"directional":{"ce":35,"pe":65}}
        }}""").asJsonObject

    @Test fun oppositeIndexPreferencesAreIndependentFromSharedFeedAndAuthorization() {
        val data = input()
        assertEquals("65.0%", directionalDisplay(data, "NIFTY", now).ce)
        assertEquals("35.0%", directionalDisplay(data, "BANKNIFTY", now).ce)
        assertEquals("65.0%", directionalDisplay(data, "BANKNIFTY", now).pe)
        assertEquals(listOf("NIFTY.vwap"), directionalDisplay(data, "NIFTY", now).reasons)
        assertEquals("NO_EDGE", data.getAsJsonObject("final").get("action").asString)
    }

    @Test fun missingIndexNeverFallsBackToConsolidatedProbability() {
        val data = input()
        data.add("probability_review", data.getAsJsonObject("index_probability_reviews").get("NIFTY"))
        data.getAsJsonObject("index_probability_reviews").remove("BANKNIFTY")
        assertEquals("Unavailable", directionalDisplay(data, "BANKNIFTY", now).ce)
        assertTrue(directionalDisplay(data, "BANKNIFTY", now).label.contains("Update the engine"))
    }

    @Test fun expiredFutureOrWrongScopeSignalsCannotLookLive() {
        val data = input()
        assertEquals("Unavailable", directionalDisplay(data, "NIFTY", now.plusSeconds(61)).ce)
        assertEquals("Unavailable", directionalDisplay(data, "NIFTY", now.minusSeconds(10)).ce)
        data.getAsJsonObject("index_probability_reviews").getAsJsonObject("BANKNIFTY").addProperty("scope", "NIFTY")
        assertEquals("Unavailable", directionalDisplay(data, "BANKNIFTY", now).ce)
    }

    @Test fun restoredSignalsAreNotLiveButExplicitNeutralPriorsRemainLabeled() {
        val data = input()
        data.addProperty("restored_from_audit", true)
        assertEquals("Unavailable", directionalDisplay(data, "NIFTY", now).ce)
        val review = data.getAsJsonObject("index_probability_reviews").getAsJsonObject("NIFTY")
        review.addProperty("status", "PRIOR_ONLY")
        review.addProperty("fresh_evidence", false)
        review.getAsJsonObject("directional").addProperty("ce", 50)
        review.getAsJsonObject("directional").addProperty("pe", 50)
        assertEquals("50.0%", directionalDisplay(data, "NIFTY", now).ce)
        assertTrue(directionalDisplay(data, "NIFTY", now).label.contains("Neutral prior"))
    }
}
