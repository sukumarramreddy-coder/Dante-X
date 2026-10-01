package com.dantex.console.data

import com.google.gson.JsonElement
import com.google.gson.JsonObject

fun JsonElement?.objectOrNull(): JsonObject? =
    if (this != null && isJsonObject) asJsonObject else null

fun JsonObject.string(name: String): String? =
    get(name)?.takeUnless { it.isJsonNull }?.let {
        runCatching { it.asString }.getOrNull()
    }

fun JsonObject.double(name: String): Double? =
    get(name)?.takeUnless { it.isJsonNull }?.let {
        runCatching { it.asDouble }.getOrNull()
    }

fun JsonObject.bool(name: String): Boolean? =
    get(name)?.takeUnless { it.isJsonNull }?.let {
        runCatching { it.asBoolean }.getOrNull()
    }

fun JsonObject.obj(name: String): JsonObject? =
    get(name)?.objectOrNull()

fun JsonObject.firstObject(vararg names: String): JsonObject? {
    for (name in names) {
        obj(name)?.let { return it }
    }
    return null
}

fun JsonObject.firstString(vararg names: String): String? {
    for (name in names) {
        string(name)?.let { return it }
    }
    return null
}

fun JsonObject.firstDouble(vararg names: String): Double? {
    for (name in names) {
        double(name)?.let { return it }
    }
    return null
}
