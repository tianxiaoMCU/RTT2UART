#include <stdint.h>
#include "SEGGER_RTT.h"

extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
void Reset_Handler(void);
#ifdef RTT_FAULT_CYCLE
void fault_cycle_init(void);
void fault_cycle_poll(volatile uint32_t *received, volatile uint32_t *written);
#endif
#ifdef CORE_OBSERVER
void core_observer_init(void);
void core_observer_poll(void);
#endif

static void fault(void) {
    for (;;) {
    }
}

__attribute__((section(".isr_vector"), used))
const uintptr_t vectors[16] = {
    (uintptr_t)&_estack, (uintptr_t)Reset_Handler,
    [2 ... 15] = (uintptr_t)fault
};

/* Readable by the debugger without adding commands to the raw echo stream. */
volatile struct {
    uint32_t signature, received_bytes, echoed_bytes, iterations;
} test_stats = {0x48525454, 0, 0, 0};

void Reset_Handler(void) {
    uint32_t *source = &_sidata;
    for (uint32_t *dest = &_sdata; dest < &_edata; ++dest) {
        *dest = *source++;
    }
    for (uint32_t *dest = &_sbss; dest < &_ebss; ++dest) {
        *dest = 0;
    }
    *(volatile uint32_t *)0xE000ED08 = (uint32_t)vectors;
    __asm volatile ("dsb\nisb" ::: "memory");

    /* Keep reset-default HSI, disabled caches/interrupts and untouched GPIO. */
#ifdef CORE_OBSERVER
    core_observer_init();
#endif
    SEGGER_RTT_Init();
#ifdef RTT_FAULT_CYCLE
    static const char banner[] = "RTT2UART-H750-FAULT/1\r\n";
    fault_cycle_init();
#else
    static const char banner[] = "RTT2UART-H750-ECHO/1\r\n";
#endif
    SEGGER_RTT_Write(0, banner, sizeof(banner) - 1);
    for (;;) {
#ifdef CORE_OBSERVER
        core_observer_poll();
#endif
#ifdef RTT_FAULT_CYCLE
        fault_cycle_poll(&test_stats.received_bytes, &test_stats.echoed_bytes);
#else
        unsigned char data[256];
        unsigned available = SEGGER_RTT_GetAvailWriteSpace(0);
        if (available > sizeof(data)) {
            available = sizeof(data);
        }
        unsigned count = SEGGER_RTT_Read(0, data, available);
        test_stats.received_bytes += count;
        if (count) {
            unsigned written = SEGGER_RTT_Write(0, data, count);
            test_stats.echoed_bytes += written;
            if (written != count) {
                fault();
            }
        }
#endif
        ++test_stats.iterations;
    }
}
