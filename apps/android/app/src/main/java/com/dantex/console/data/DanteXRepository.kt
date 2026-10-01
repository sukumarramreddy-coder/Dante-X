package com.dantex.console.data

import com.google.gson.JsonElement
import com.google.gson.JsonNull

data class EndpointResult(
    val data: JsonElement = JsonNull.INSTANCE,
    val error: String? = null
) {
    val available: Boolean
        get() = error == null && !data.isJsonNull
}

data class DashboardSnapshot(
    val health: JsonElement,
    val decision: EndpointResult,
    val calibration: EndpointResult,
    val expert: EndpointResult,
    val signals: EndpointResult,
    val observation: EndpointResult,
    val market: EndpointResult
)

class DanteXRepository(
    private val api: DanteXApi = DanteXClient.api
) {

    suspend fun dashboard(): DashboardSnapshot {

        // If this fails, the backend really is unreachable.
        val health = api.health()

        // Everything below is independently fault tolerant.
        val decision = safe { api.currentDecision() }
        val calibration = safe { api.calibration() }
        val expert = safe { api.expertStatus() }
        val signals = safe { api.signals() }
        val observation = safe { api.observationStatus() }
        val market = safe { api.marketState() }

        return DashboardSnapshot(
            health = health,
            decision = decision,
            calibration = calibration,
            expert = expert,
            signals = signals,
            observation = observation,
            market = market
        )
    }

    private suspend fun safe(
        call: suspend () -> JsonElement
    ): EndpointResult {
        return try {
            EndpointResult(data = call())
        } catch (e: Exception) {
            EndpointResult(
                error = e.message ?: e::class.java.simpleName
            )
        }
    }
}
