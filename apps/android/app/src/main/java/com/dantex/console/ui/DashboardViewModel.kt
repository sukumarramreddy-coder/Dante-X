package com.dantex.console.ui

import androidx.lifecycle.ViewModel
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

class DashboardViewModel(
    private val repository: DanteXRepository = DanteXRepository()
) : ViewModel() {

    private val _state =
        MutableStateFlow<DashboardState>(DashboardState.Loading)

    val state: StateFlow<DashboardState> = _state.asStateFlow()

    private var pollingJob: Job? = null

    init {
        startPolling()
    }

    fun refresh() {
        viewModelScope.launch {
            load()
        }
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
        } catch (e: Exception) {
            _state.value = DashboardState.Error(
                e.message ?: e::class.java.simpleName
            )
        }
    }
}
