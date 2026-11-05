#include <stdint.h>
#include "SEGGER_RTT.h"

#define SYSTICK_CTRL (*(volatile uint32_t *)0xE000E010)
#define SYSTICK_LOAD (*(volatile uint32_t *)0xE000E014)
#define SYSTICK_VAL  (*(volatile uint32_t *)0xE000E018)
#define DELAY_MS 3000u
#define OFF_MS 15000u

static const unsigned char command[] = "\x1b[H05:RTT-OFF]\r\n";
static const char ack[] = "H05 ACK delay=3000ms off=15000ms\r\n";
static const char resumed[] = "H05 RESUMED\r\n";
static unsigned matched;

/* Phase: 0 normal, 1 acknowledged delay, 2 RTT off. No host writes required. */
volatile struct {
    uint32_t signature, phase, milliseconds, commands, off_count, resume_count;
    uint32_t ack_ms, off_ms, resume_ms, discarded_on_resume, write_errors;
} fault_stats;

static unsigned emit(const void *data, unsigned size, volatile uint32_t *written) {
    unsigned count = SEGGER_RTT_Write(0, data, size);
    *written += count;
    if (count != size) {
        ++fault_stats.write_errors;
    }
    return count == size;
}

void fault_cycle_init(void) {
    fault_stats.signature = 0x48303546u;
    /* Reset-default HSI/core 64 MHz; poll 1 ms ticks without enabling interrupts. */
    SYSTICK_CTRL = 0;
    SYSTICK_LOAD = 64000u - 1u;
    SYSTICK_VAL = 0;
    SYSTICK_CTRL = 5;
}

void fault_cycle_poll(volatile uint32_t *received, volatile uint32_t *written) {
    volatile SEGGER_RTT_CB *cb = &_SEGGER_RTT;
    if (SYSTICK_CTRL & (1u << 16)) {
        ++fault_stats.milliseconds;
    }
    uint32_t now = fault_stats.milliseconds;
    if (fault_stats.phase == 1 && now - fault_stats.ack_ms >= DELAY_MS) {
        for (unsigned i = 0; i < sizeof(cb->acID); ++i) {
            cb->acID[i] = 0;
        }
        cb->MaxNumUpBuffers = 0;
        cb->MaxNumDownBuffers = 0;
        cb->aUp[0].SizeOfBuffer = 0;
        cb->aDown[0].SizeOfBuffer = 0;
        __asm volatile ("dsb" ::: "memory");
        fault_stats.off_ms = now;
        ++fault_stats.off_count;
        fault_stats.phase = 2;
    }
    if (fault_stats.phase == 2) {
        if (now - fault_stats.off_ms >= OFF_MS) {
            unsigned wr = cb->aDown[0].WrOff;
            unsigned rd = cb->aDown[0].RdOff;
            if (wr < 4096u && rd < 4096u) {
                fault_stats.discarded_on_resume += (wr + 4096u - rd) % 4096u;
            }
            /* Reinitialize both rings before publishing the valid RTT ID again. */
            SEGGER_RTT_Init();
            matched = 0;
            fault_stats.resume_ms = now;
            ++fault_stats.resume_count;
            fault_stats.phase = 0;
            emit(resumed, sizeof(resumed) - 1, written);
        }
        return;  /* In the off window there are no RTT API calls. */
    }
    if (SEGGER_RTT_GetAvailWriteSpace(0) < sizeof(ack) + sizeof(command)) {
        return;
    }
    unsigned char value;
    if (SEGGER_RTT_Read(0, &value, 1) != 1) {
        return;
    }
    ++*received;
    if (fault_stats.phase == 1) {
        emit(&value, 1, written);
        return;
    }
    if (value == command[matched]) {
        if (++matched == sizeof(command) - 1) {
            matched = 0;
            if (emit(ack, sizeof(ack) - 1, written)) {
                fault_stats.ack_ms = now;
                ++fault_stats.commands;
                fault_stats.phase = 1;
            }
        }
        return;
    }
    if (matched) {
        emit(command, matched, written);
        matched = 0;
    }
    if (value == command[0]) {
        matched = 1;
    } else {
        emit(&value, 1, written);
    }
}
