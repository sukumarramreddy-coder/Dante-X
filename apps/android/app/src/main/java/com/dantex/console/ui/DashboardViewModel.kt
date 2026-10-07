package com.dantex.console.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.dantex.console.data.EngineSettings
import com.dantex.console.data.DanteXClient
import com.dantex.console.data.normalizeEngineUrl
import kotlinx.coroutines.CancellationException
import androidx.lifecycle.viewModelScope
import com.dantex.console.data.DanteXRepository
import com.dantex.console.data.DashboardSnapshot
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

sealed interface DashboardState {
    data object Loading : DashboardState

    data class Ready(
        val snapshot: DashboardSnapshot
    ) : DashboardState

    data class Error(
        val message: String
    ) : DashboardState
}

class DashboardViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = EngineSettings(application)
    private val repository = DanteXRepository { DanteXClient.create(settings.baseUrl) }
    private val _baseUrl = MutableStateFlow(settings.baseUrl)
    val baseUrl = _baseUrl.asStateFlow()
    private val _connectionStatus = MutableStateFlow("Not tested")
    val connectionStatus = _connectionStatus.asStateFlow()
    private var testJob: Job? = null

    fun saveUrl(value: String) {
        try {
            _baseUrl.value = settings.save(value)
            testJob?.cancel()
            _connectionStatus.value = "Saved. Connecting to ${settings.baseUrl}"
            _state.value = DashboardState.Loading
            refresh()
        } catch (e: Exception) {
            _connectionStatus.value = e.message ?: "Unable to save address"
        }
    }

    fun testConnection(value: String) {
        testJob?.cancel()
        testJob = viewModelScope.launch {
            try {
                val url = normalizeEngineUrl(value)
                _connectionStatus.value = "Testing ${url}health..."
                val health = DanteXClient.create(url).health()
                check(health.isJsonObject && health.asJsonObject.has("status")) { "Unexpected /health response" }
                _connectionStatus.value = "Reached ${url}health - status: ${health.asJsonObject.get("status")}. Test does not save the address or authorize trading."
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _connectionStatus.value = "Connection failed: ${e.message ?: e::class.java.simpleName}. Check engine address, port and Wi-Fi."
            }
        }
    }

    private val _state =
        MutableStateFlow<DashboardState>(DashboardState.Loading)

    val state: StateFlow<DashboardState> = _state.asStateFlow()

    private var pollingJob: Job? = null

    init {
        startPolling()
    }

    fun refresh() {
        pollingJob?.cancel()
        pollingJob = null
        startPolling()
    }

    private fun startPolling() {
        if (pollingJob != null) return

        pollingJob = viewModelScope.launch {
            while (isActive) {
                load()
                delay(5_000)
            }
        }
    }

    private suspend fun load() {
        try {
            val snapshot = repository.dashboard()
            _state.value = DashboardState.Ready(snapshot)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            _state.value = DashboardState.Error(
                e.message ?: e::class.java.simpleName
            )
        }
    }
}
