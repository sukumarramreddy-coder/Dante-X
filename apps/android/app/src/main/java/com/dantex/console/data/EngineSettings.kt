package com.dantex.console.data

import android.content.Context
import com.dantex.console.BuildConfig
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

fun normalizeEngineUrl(value: String): String {
    val url = value.trim().toHttpUrlOrNull()
        ?: throw IllegalArgumentException("Enter a valid HTTP or HTTPS URL, including the engine port.")
    require(url.username.isEmpty() && url.password.isEmpty()) { "Credentials must not be included in the URL." }
    require(url.query == null && url.fragment == null && url.encodedPath == "/") {
        "Use the engine root address without a path, query or fragment."
    }
    return url.toString()
}

class EngineAddressStore(
    private val read: () -> String?,
    private val write: (String) -> Boolean
) {
    val baseUrl: String
        get() = runCatching { normalizeEngineUrl(read() ?: BuildConfig.DANTEX_BASE_URL) }
            .getOrDefault(BuildConfig.DANTEX_BASE_URL)
    fun save(value: String): String {
        val normalized = normalizeEngineUrl(value)
        check(write(normalized)) { "Could not save engine address." }
        return normalized
    }
}

class EngineSettings(context: Context) {
    private val preferences = context.getSharedPreferences("engine_connection", Context.MODE_PRIVATE)
    private val store = EngineAddressStore(
        read = { preferences.getString("base_url", null) },
        write = { preferences.edit().putString("base_url", it).commit() }
    )
    val baseUrl: String get() = store.baseUrl
    fun save(value: String): String = store.save(value)
}
