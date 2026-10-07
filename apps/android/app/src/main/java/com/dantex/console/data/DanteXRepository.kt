package com.dantex.console.data

import com.google.gson.JsonElement
import com.google.gson.JsonNull
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

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
    private val apiProvider: () -> DanteXApi
) {

    suspend fun dashboard(): DashboardSnapshot = coroutineScope {

        val api = apiProvider()
        // Use one address for the entire snapshot.
        val health = api.health()

        // Everything below is independently fault tolerant.
        val decision = async { safe { api.currentDecision() } }
        val calibration = async { safe { api.calibration() } }
        val expert = async { safe { api.expertStatus() } }
        val signals = async { safe { api.signals() } }
        val observation = async { safe { api.observationStatus() } }
        val market = async { safe { api.marketState() } }

        DashboardSnapshot(
            health = health,
            decision = decision.await(),
            calibration = calibration.await(),
            expert = expert.await(),
            signals = signals.await(),
            observation = observation.await(),
            market = market.await()
        )
    }

    private suspend fun safe(
        call: suspend () -> JsonElement
    ): EndpointResult {
        return try {
            EndpointResult(data = call())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            EndpointResult(
                error = e.message ?: e::class.java.simpleName
            )
        }
    }
}
