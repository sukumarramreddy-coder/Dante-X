package com.dantex.console.data

import com.google.gson.JsonElement
import retrofit2.http.GET

interface DanteXApi {

    @GET("health")
    suspend fun health(): JsonElement

    @GET("v1/decision/current")
    suspend fun currentDecision(): JsonElement

    @GET("v1/calibration/learning")
    suspend fun calibration(): JsonElement

    @GET("v1/expert/status")
    suspend fun expertStatus(): JsonElement

    @GET("v1/signals")
    suspend fun signals(): JsonElement

    @GET("v1/observation/status")
    suspend fun observationStatus(): JsonElement

    @GET("v1/market/state")
    suspend fun marketState(): JsonElement
}
