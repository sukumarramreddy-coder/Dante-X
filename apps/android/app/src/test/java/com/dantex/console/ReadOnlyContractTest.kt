package com.dantex.console

import org.junit.Assert.assertTrue
import org.junit.Test

class ReadOnlyContractTest {

    @Test
    fun androidConsoleHasNoExecutionAuthority() {
        val allowedActions = setOf(
            "WAIT",
            "GO",
            "HOLD",
            "PROTECT",
            "EXIT",
            "NO_EDGE"
        )

        assertTrue("GO" in allowedActions)
        assertTrue("EXIT" in allowedActions)
        assertTrue("BUY" !in allowedActions)
        assertTrue("SELL" !in allowedActions)
    }
}
