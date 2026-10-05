package com.dantex.console

import com.dantex.console.data.*
import java.net.ServerSocket
import kotlin.concurrent.thread
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class EngineConnectionTest {
    @Test fun savedAddressSurvivesStoreRecreationAndInvalidEdits() {
        var persisted: String? = null
        fun store() = EngineAddressStore({ persisted }, { persisted = it; true })
        assertEquals("http://192.168.1.109:8000/", store().baseUrl)
        store().save("http://192.168.1.112:8000")
        assertEquals("http://192.168.1.112:8000/", store().baseUrl)
        assertThrows(IllegalArgumentException::class.java) { store().save("broken") }
        assertEquals("http://192.168.1.112:8000/", store().baseUrl)
        assertThrows(IllegalStateException::class.java) { EngineAddressStore({ persisted }, { false }).save("http://new-host:8000") }
        assertEquals("http://192.168.1.112:8000/", store().baseUrl)
        persisted = "broken"
        assertEquals("http://192.168.1.109:8000/", store().baseUrl)
    }

    @Test fun normalizesLanAndHttpsRoots() {
        assertEquals("http://192.168.1.109:8000/", normalizeEngineUrl(" http://192.168.1.109:8000 "))
        assertEquals("https://engine.example/", normalizeEngineUrl("https://engine.example"))
        assertEquals("http://[::1]:8000/", normalizeEngineUrl("http://[::1]:8000"))
    }
    @Test fun rejectsInvalidAndAmbiguousAddresses() {
        for (input in listOf("", "192.168.1.109:8000", "ftp://host", "http://host:99999", "http://user:pass@host", "http://host/v1", "http://host?x=1", "http://host#fragment")) {
            assertThrows(input, IllegalArgumentException::class.java) { normalizeEngineUrl(input) }
        }
    }
    @Test fun allRequestsFollowSelectedAddressAndHealthErrorsPropagate() = runBlocking {
        val paths = mutableListOf<String>()
        val server = ServerSocket(0)
        val worker = thread(isDaemon = true) {
            repeat(7) {
                server.accept().use { socket ->
                    val reader = socket.getInputStream().bufferedReader()
                    paths.add(reader.readLine().split(" ")[1])
                    while (!reader.readLine().isNullOrEmpty()) { }
                    val body = "{\"status\":\"ok\"}"
                    socket.getOutputStream().write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n" + body).toByteArray())
                }
            }
        }
        try {
            var selected = "http://127.0.0.1:${server.localPort}/"
            val repository = DanteXRepository { DanteXClient.create(selected) }
            assertTrue(repository.dashboard().decision.available)
            assertEquals(setOf("/health", "/v1/decision/current", "/v1/calibration/learning", "/v1/expert/status", "/v1/signals", "/v1/observation/status", "/v1/market/state"), paths.toSet())
            selected = "http://127.0.0.1:1/"
            try { repository.dashboard(); fail("Must use changed address") } catch (_: java.io.IOException) { }
        } finally { server.close(); worker.join(1000) }
    }
}
