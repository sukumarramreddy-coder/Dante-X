package com.dantex.console.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.dantex.console.data.*
import com.google.gson.JsonObject
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val Ink = Color(0xFF0D1422)
private val Panel = Color(0xFF182233)
private val Muted = Color(0xFFAFBDD0)
private val CeColor = Color(0xFF75DCC1)
private val PeColor = Color(0xFFFFBD90)

@Composable
fun DanteXApp(vm: DashboardViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val savedUrl by vm.baseUrl.collectAsStateWithLifecycle()
    val connectionStatus by vm.connectionStatus.collectAsStateWithLifecycle()
    var settingsOpen by rememberSaveable { mutableStateOf(false) }
    BackHandler(enabled = settingsOpen) { settingsOpen = false }
    MaterialTheme(colorScheme = darkColorScheme(
        primary = CeColor, onPrimary = Ink, background = Ink, surface = Panel,
        onSurface = Color(0xFFF0F4FA), onBackground = Color(0xFFF0F4FA)
    )) {
        Surface(Modifier.fillMaxSize(), color = Ink) {
            Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding()
                .verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween) {
                    Column {
                        Text(if (settingsOpen) "Settings" else "DANTE-X",
                            style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text("SHADOW OBSERVATION", color = Muted,
                            style = MaterialTheme.typography.labelSmall)
                    }
                    TextButton(onClick = { settingsOpen = !settingsOpen }) {
                        Text(if (settingsOpen) "Done" else "Settings")
                    }
                }
                if (settingsOpen) {
                    ConnectionSettings(savedUrl, connectionStatus, vm::saveUrl, vm::testConnection)
                } else when (val current = state) {
                    DashboardState.Loading -> {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text("Connecting to your engine", style = MaterialTheme.typography.titleMedium)
                        Text("Connection settings are available in Settings.", color = Muted)
                    }
                    is DashboardState.Error -> {
                        Text("Engine unavailable", style = MaterialTheme.typography.headlineSmall)
                        Text("Check that the laptop engine is running and both devices are on the same network.", color = Muted)
                        Button(onClick = vm::refresh) { Text("Try again") }
                        ExpandableDetails("Connection details") { Text(current.message, color = Muted) }
                    }
                    is DashboardState.Ready -> DashboardContent(current.snapshot, vm::refresh)
                }
            }
        }
    }
}

@Composable
private fun ConnectionSettings(savedUrl: String, status: String,
                               onSave: (String) -> Unit, onTest: (String) -> Unit) {
    var draft by rememberSaveable(savedUrl) { mutableStateOf(savedUrl) }
    Text("Engine connection", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
    Text("Use your laptop's address. Save a new address here if your Wi-Fi assigns a different one.", color = Muted)
    OutlinedTextField(value = draft, onValueChange = { draft = it }, singleLine = true,
        label = { Text("Engine / API Base URL") }, modifier = Modifier.fillMaxWidth())
    Button(onClick = { onSave(draft) }, modifier = Modifier.fillMaxWidth()) { Text("Save & Connect") }
    OutlinedButton(onClick = { onTest(draft) }, modifier = Modifier.fillMaxWidth()) { Text("Test Connection") }
    Text(status, color = Muted)
    Text("Active address: $savedUrl", style = MaterialTheme.typography.bodySmall, color = Muted)
    Text("Test Connection checks this address without saving it.", style = MaterialTheme.typography.bodySmall, color = Muted)
}

@Composable
private fun DashboardContent(snapshot: DashboardSnapshot, onRefresh: () -> Unit) {
    val decision = snapshot.decision.data.objectOrNull()
    val action = decision?.obj("final")?.firstString("action") ?: "NO_EDGE"
    val health = snapshot.health.objectOrNull()
    val marketClosed = snapshot.observation.data.objectOrNull()?.firstString("state") == "MARKET_CLOSED"
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(if (marketClosed) "Market closed" else if (decision?.bool("feed_fresh") == true) "Live observation" else "Waiting for fresh data",
                fontWeight = FontWeight.SemiBold)
            Text("Updated ${displayTime(decision?.firstString("timestamp"))}",
                color = Muted, style = MaterialTheme.typography.bodySmall)
        }
        Surface(color = Color(0xFF26364C), shape = RoundedCornerShape(20.dp)) {
            Text(action.replace('_', ' '), Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                style = MaterialTheme.typography.labelLarge)
        }
    }
    IndexCard("NIFTY", decision)
    IndexCard("BANKNIFTY", decision)
    Text("Provisional directional estimates. Uncalibrated; not profit odds. Trade authorization is evaluated separately.",
        style = MaterialTheme.typography.bodySmall, color = Muted)
    OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("Refresh") }
    ExpandableDetails("Engine & data status") {
        Text("Connection: online", color = Muted)
        Text("Engine: ${health?.firstString("status") ?: "unknown"}", color = Muted)
        listOf("Decision" to snapshot.decision, "Calibration" to snapshot.calibration,
            "Expert review" to snapshot.expert, "Signals" to snapshot.signals,
            "Observation" to snapshot.observation, "Market" to snapshot.market).forEach { (name, result) ->
            Text("$name: ${if (result.available) "available" else result.error ?: "unavailable"}",
                color = Muted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun IndexCard(symbol: String, decision: JsonObject?) {
    val display = directionalDisplay(decision, symbol)
    val candidates = decision?.obj("deterministic")?.get("candidates")
        ?.takeIf { it.isJsonArray }?.asJsonArray?.mapNotNull { it.objectOrNull() }
        ?.filter { it.firstString("instrument") == symbol } ?: emptyList()
    val review = decision?.obj("index_probability_reviews")?.obj(symbol)
    val quality = when {
        display.ce == "Unavailable" -> "Unavailable"
        review?.string("status") == "PRIOR_ONLY" -> "Neutral prior"
        else -> "Provisional"
    }
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Panel)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(if (symbol == "BANKNIFTY") "BANK NIFTY" else symbol,
                    style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(quality, style = MaterialTheme.typography.labelMedium, color = Muted)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                ProbabilityValue("CE", display.ce, CeColor, Modifier.weight(1f))
                ProbabilityValue("PE", display.pe, PeColor, Modifier.weight(1f))
            }
            Text(if (quality == "Provisional") "Own-index evidence. Uncalibrated." else display.label,
                color = Muted, style = MaterialTheme.typography.bodySmall)
            HorizontalDivider(color = Color(0xFF2B384D))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                for (side in listOf("CE", "PE")) {
                    val candidate = candidates.firstOrNull { it.firstString("side") == side }
                    Text("$side  ${candidate?.firstString("action")?.replace('_', ' ') ?: "NO EDGE"}",
                        style = MaterialTheme.typography.labelLarge, color = Muted)
                }
            }
            ExpandableDetails("Evidence & blockers") {
                Text(display.quality, color = Muted)
                for (side in listOf("CE", "PE")) {
                    val candidate = candidates.firstOrNull { it.firstString("side") == side }
                    Text("$side evidence score: ${candidate?.firstDouble("directional_score") ?: "Unavailable"}", color = Muted)
                }
                (display.reasons + candidates.flatMap { it.get("missing_data").strings() }).distinct().forEach {
                    Text(it.replace('_', ' '), color = Muted, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun ProbabilityValue(side: String, value: String, tint: Color, modifier: Modifier) {
    Column(modifier.background(Ink, RoundedCornerShape(16.dp)).padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(side, color = tint, style = MaterialTheme.typography.labelLarge)
        Text(if (value == "Unavailable") "--" else value, color = tint,
            style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ExpandableDetails(title: String, content: @Composable ColumnScope.() -> Unit) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    Column {
        TextButton(onClick = { expanded = !expanded }, contentPadding = PaddingValues(0.dp)) {
            Text(if (expanded) "$title -" else "$title +")
        }
        if (expanded) Column(verticalArrangement = Arrangement.spacedBy(6.dp), content = content)
    }
}

private fun displayTime(value: String?): String = runCatching {
    OffsetDateTime.parse(value).atZoneSameInstant(ZoneId.of("Asia/Kolkata"))
        .format(DateTimeFormatter.ofPattern("dd MMM, HH:mm:ss 'IST'"))
}.getOrDefault("not available")
