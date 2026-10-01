package com.dantex.console.data

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName

data class HealthResponse(
    val status: String? = null,
    val service: String? = null,
    @SerializedName("live_data")
    val liveData: LiveDataHealth? = null
)

data class LiveDataHealth(
    val status: String? = null,
    @SerializedName("age_seconds")
    val ageSeconds: Double? = null,
    val eligible: Boolean? = null,
    @SerializedName("last_sample_at")
    val lastSampleAt: String? = null,
    @SerializedName("last_persisted_at")
    val lastPersistedAt: String? = null
)

data class DecisionResponse(
    @SerializedName("schema_version")
    val schemaVersion: String? = null,
    val status: String? = null,
    val timestamp: String? = null,
    @SerializedName("snapshot_id")
    val snapshotId: String? = null,
    @SerializedName("feed_fresh")
    val feedFresh: Boolean? = null,
    @SerializedName("age_seconds")
    val ageSeconds: Double? = null,
    @SerializedName("missing_data")
    val missingData: List<String>? = null,
    val mode: String? = null,
    val deterministic: JsonElement? = null,
    val final: JsonElement? = null,
    @SerializedName("expert_provider_status")
    val expertProviderStatus: JsonElement? = null,
    @SerializedName("runtime_error")
    val runtimeError: String? = null
)

data class CalibrationResponse(
    val status: String? = null,
    val phase: String? = null,
    @SerializedName("calibration_status")
    val calibrationStatus: String? = null,
    @SerializedName("learning_sessions")
    val learningSessions: Int? = null,
    @SerializedName("validation_sessions")
    val validationSessions: Int? = null,
    @SerializedName("completed_sessions")
    val completedSessions: Int? = null,
    @SerializedName("minimum_sessions")
    val minimumSessions: Int? = null
)

data class SignalSnapshot(
    val current: JsonElement? = null,
    val events: List<JsonElement>? = null,
    val mode: String? = null,
    val probability: Double? = null,
    @SerializedName("calibration_status")
    val calibrationStatus: String? = null
)

data class ExpertStatusResponse(
    val status: String? = null,
    val provider: String? = null,
    val enabled: Boolean? = null,
    val configured: Boolean? = null
)
