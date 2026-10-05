package com.dantex.console.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.dantex.console.data.directionalDisplay
import com.dantex.console.data.obj
import com.dantex.console.data.strings
import com.dantex.console.data.DashboardSnapshot
import com.dantex.console.data.EndpointResult
import com.dantex.console.data.firstDouble
import com.dantex.console.data.firstObject
import com.dantex.console.data.firstString
import com.dantex.console.data.objectOrNull

@Composable
fun DanteXApp(
    vm: DashboardViewModel = viewModel()
) {
    val state by vm.state.collectAsState()
    val savedUrl by vm.baseUrl.collectAsState()
    val connectionStatus by vm.connectionStatus.collectAsState()
    var draftUrl by remember(savedUrl) { mutableStateOf(savedUrl) }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Text("Engine / API Base URL", fontWeight = FontWeight.Bold)
                    OutlinedTextField(value = draftUrl, onValueChange = { draftUrl = it },
                        singleLine = true, modifier = Modifier.fillMaxWidth(),
                        label = { Text("http://192.168.1.109:8000") })
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.saveUrl(draftUrl) }) { Text("Save & Connect") }
                        Button(onClick = { vm.testConnection(draftUrl) }) { Text("Test Connection") }
                    }
                    Text("Saved: $savedUrl", style = MaterialTheme.typography.bodySmall)
                    Text(connectionStatus, style = MaterialTheme.typography.bodySmall)
                }
                when (val current = state) {

                DashboardState.Loading ->
                    LoadingScreen()

                is DashboardState.Error ->
                    OfflineScreen(
                        message = current.message,
                        onRetry = vm::refresh
                    )

                is DashboardState.Ready ->
                    DashboardScreen(
                        snapshot = current.snapshot,
                        onRefresh = vm::refresh
                    )
                }
            }
        }
    }
}

@Composable
private fun LoadingScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "DANTE-X",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Black
        )

        Spacer(Modifier.height(8.dp))

        Text("Connecting to shadow engine...")
    }
}

@Composable
private fun OfflineScreen(
    message: String,
    onRetry: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "DANTE-X • OFFLINE",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Black
        )

        Spacer(Modifier.height(12.dp))

        Text(message)

        Spacer(Modifier.height(20.dp))

        Button(onClick = onRetry) {
            Text("Retry")
        }

        Spacer(Modifier.height(16.dp))

        Text(
            "No broker execution capability.",
            style = MaterialTheme.typography.bodySmall
        )
    }
}

@Composable
private fun DashboardScreen(
    snapshot: DashboardSnapshot,
    onRefresh: () -> Unit
) {
    val health = snapshot.health.objectOrNull()

    val healthStatus =
        health?.firstString(
            "status",
            "state"
        ) ?: "UNKNOWN"

    val decision =
        snapshot.decision.data.objectOrNull()

    val final =
        decision?.firstObject("final")

    val action =
        final?.firstString(
            "action",
            "status"
        )
            ?: decision?.firstString(
                "action",
                "status"
            )
            ?: "NO_EDGE"

    val calibration =
        final?.firstString(
            "calibration_status"
        )
            ?: snapshot.calibration.data
                .objectOrNull()
                ?.firstString(
                    "calibration_status",
                    "status",
                    "phase"
                )
            ?: "UNCALIBRATED"

    val display = directionalDisplay(snapshot.decision.data)

    val feedFresh =
        decision
            ?.get("feed_fresh")
            ?.takeUnless { it.isJsonNull }
            ?.let {
                runCatching { it.asBoolean }.getOrNull()
            }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {

        Text(
            "DANTE-X",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Black
        )

        Text(
            "SHADOW • READ ONLY",
            style = MaterialTheme.typography.titleMedium
        )

        Spacer(Modifier.height(16.dp))

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {

                Text(
                    action,
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Black
                )

                Spacer(Modifier.height(8.dp))

                KeyValue(
                    "Engine",
                    healthStatus.uppercase()
                )

                KeyValue(
                    "Connection",
                    "ONLINE"
                )

                KeyValue(
                    "Feed",
                    when (feedFresh) {
                        true -> "FRESH"
                        false -> "STALE / WAITING"
                        null -> "UNKNOWN"
                    }
                )

                KeyValue("CE directional probability", display.ce)
                KeyValue("PE directional probability", display.pe)
                Text("NIFTY directional preference with BANKNIFTY confirmation")
                Text(display.label)
                Text("Data quality: ${display.quality}")
                Text("Observed at: ${decision?.firstString("timestamp") ?: "Not recorded"}")
                display.reasons.forEach { Text("• ${it.replace('_', ' ')}") }

                KeyValue(
                    "Calibration",
                    calibration
                )

                KeyValue(
                    "Mode",
                    decision?.firstString("mode")
                        ?: "shadow"
                )
            }
        }

        Spacer(Modifier.height(12.dp))

        IndexCard(
            name = "NIFTY",
            decision = decision
        )

        Spacer(Modifier.height(12.dp))

        IndexCard(
            name = "BANKNIFTY",
            decision = decision
        )

        Spacer(Modifier.height(12.dp))

        EndpointCard(
            title = "Decision Runtime",
            result = snapshot.decision
        )

        Spacer(Modifier.height(8.dp))

        EndpointCard(
            title = "Calibration",
            result = snapshot.calibration
        )

        Spacer(Modifier.height(8.dp))

        EndpointCard(
            title = "Expert Layer",
            result = snapshot.expert
        )

        Spacer(Modifier.height(8.dp))

        EndpointCard(
            title = "Signals",
            result = snapshot.signals
        )

        Spacer(Modifier.height(8.dp))

        EndpointCard(
            title = "Observation",
            result = snapshot.observation
        )

        Spacer(Modifier.height(8.dp))

        EndpointCard(
            title = "Market State",
            result = snapshot.market
        )

        Spacer(Modifier.height(16.dp))

        Button(
            onClick = onRefresh,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Refresh")
        }

        Spacer(Modifier.height(16.dp))

        HorizontalDivider()

        Spacer(Modifier.height(12.dp))

        Text(
            "Android is a read-only observer. " +
                "Directional preferences remain heuristic and uncalibrated; authorization is independent.",
            style = MaterialTheme.typography.bodySmall
        )

        Text(
            "Backend contract: additive probability_review; shadow only",
            style = MaterialTheme.typography.bodySmall
        )
    }
}

@Composable
private fun IndexCard(name: String, decision: com.google.gson.JsonObject?) {
    val candidates = decision?.obj("deterministic")?.get("candidates")
        ?.takeIf { it.isJsonArray }?.asJsonArray
        ?.mapNotNull { it.objectOrNull() }
        ?.filter { it.firstString("instrument") == name } ?: emptyList()
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Independent four-way evidence scores; not probabilities.")
            for (side in listOf("CE", "PE")) {
                val candidate = candidates.firstOrNull { it.firstString("side") == side }
                KeyValue(side + " evidence score", candidate?.firstDouble("directional_score")?.toString() ?: "Unavailable")
                KeyValue(side + " state", candidate?.firstString("action") ?: "NO_EDGE")
            }
            val reasons = candidates.flatMap { it.get("missing_data").strings() }.distinct()
            reasons.forEach { Text("• ${it.replace('_', ' ')}") }
        }
    }
}

@Composable
private fun EndpointCard(
    title: String,
    result: EndpointResult
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {

            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Spacer(Modifier.height(4.dp))

            if (result.available) {
                Text(
                    "AVAILABLE",
                    fontWeight = FontWeight.SemiBold
                )
            } else {
                Text(
                    "UNAVAILABLE"
                )

                result.error?.let {
                    Spacer(Modifier.height(4.dp))

                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}

@Composable
private fun KeyValue(
    key: String,
    value: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        horizontalArrangement =
            Arrangement.SpaceBetween
    ) {
        Text(key)

        Text(
            value,
            fontWeight = FontWeight.SemiBold
        )
    }
}
