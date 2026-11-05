#include <stdint.h>

#define REG(address) (*(volatile uint32_t *)(address))
#define TIMER 0x40000000u
#define FROZEN_TIMER 0x40000C00u
#define FREEZE REG(0x5C00103Cu)
#define RCC REG(0x58024400u)
#define MAGIC 0x48303854u
#define CLOCK_HZ 64000000u
#define THRESHOLD 6400u
#define DURATION 2880000000u
#define CAPACITY 64u

/* Retained across tested warm resets; never interpreted as power-loss storage. */
__attribute__((section(".noinit"))) volatile struct {
    uint32_t magic, inverse_magic, boots, inverse_boots;
    uint32_t request, acknowledged, state, start_boot;
    uint32_t elapsed_ticks, samples, events, dropped, invalid_samples;
    uint32_t max_lag, max_lead, reset_flags, config_mask;
    uint32_t duration_ticks, threshold_ticks, clock_hz;
    uint32_t sealed_boot, sealed_reset_flags;
    struct {
        uint32_t kind, boot, ticks, timer_delta, running_delta;
        int32_t lag;
        uint32_t config_mask, reset_flags;
    } log[CAPACITY];
} core_observer;

static uint32_t last_timer, last_running;

static void seal(uint32_t state) {
    core_observer.sealed_boot = core_observer.boots;
    core_observer.sealed_reset_flags = core_observer.reset_flags;
    core_observer.state = state;
}

static void event(uint32_t kind, uint32_t dt, uint32_t dc, int32_t lag, uint32_t mask) {
    uint32_t n = core_observer.events++;
    if (n >= CAPACITY) {
        ++core_observer.dropped;
        return;
    }
    core_observer.log[n].kind = kind;
    core_observer.log[n].boot = core_observer.boots;
    core_observer.log[n].ticks = core_observer.elapsed_ticks;
    core_observer.log[n].timer_delta = dt;
    core_observer.log[n].running_delta = dc;
    core_observer.log[n].lag = lag;
    core_observer.log[n].config_mask = mask;
    core_observer.log[n].reset_flags = core_observer.reset_flags;
}

static uint32_t configuration(void) {
    uint32_t mask = 0;
    if (FREEZE & 1u) mask |= 1u;
    if (!(FREEZE & 8u)) mask |= 2u;
    if (REG(FROZEN_TIMER) != 1u || REG(FROZEN_TIMER + 0x28u) != 0u ||
        REG(FROZEN_TIMER + 0x2Cu) != 0xFFFFFFFFu) mask |= 4u;
    if (REG(TIMER) != 1u || REG(TIMER + 0x28u) != 0u ||
        REG(TIMER + 0x2Cu) != 0xFFFFFFFFu || (REG(0x580244E8u) & 9u) != 9u) mask |= 8u;
    if ((RCC & 0x18u) || (REG(0x58024410u) & 0x38u) ||
        (REG(0x58024418u) & 0xF0Fu) || (REG(0x5802441Cu) & 0x70u)) mask |= 16u;
    return mask;
}

void core_observer_init(void) {
    if (core_observer.magic != MAGIC || core_observer.inverse_magic != ~MAGIC ||
        core_observer.inverse_boots != ~core_observer.boots) {
        volatile uint32_t *words = (volatile uint32_t *)&core_observer;
        for (unsigned i = 0; i < sizeof(core_observer) / sizeof(*words); ++i) words[i] = 0;
        core_observer.magic = MAGIC;
        core_observer.inverse_magic = ~MAGIC;
    }
    ++core_observer.boots;
    core_observer.inverse_boots = ~core_observer.boots;
    core_observer.reset_flags = REG(0x580244D0u);
    REG(0x580244D0u) |= 1u << 16;  /* Clear reset flags only after recording them. */
    REG(0x580244E8u) |= 9u;
    (void)REG(0x580244E8u);
    REG(0x58024490u) |= 9u;
    REG(0x58024490u) &= ~9u;
    FREEZE = (FREEZE & ~1u) | 8u;
    const uint32_t timers[] = {TIMER, FROZEN_TIMER};
    for (unsigned i = 0; i < 2; ++i) {
        uint32_t timer = timers[i];
        REG(timer) = 0;
        REG(timer + 0x28u) = 0;
        REG(timer + 0x2Cu) = 0xFFFFFFFFu;
        REG(timer + 0x14u) = 1;
        REG(timer + 0x10u) = 0;
        REG(timer + 0x24u) = 0;
    }
    REG(FROZEN_TIMER) = 1;
    REG(TIMER) = 1;
    last_timer = REG(TIMER + 0x24u);
    last_running = REG(FROZEN_TIMER + 0x24u);
    if (core_observer.state == 1u) event(1u, 0, 0, 0, configuration());
}

void core_observer_poll(void) {
    uint32_t timer = REG(TIMER + 0x24u), running = REG(FROZEN_TIMER + 0x24u);
    uint32_t dt = timer - last_timer, dc = running - last_running;
    last_timer = timer;
    last_running = running;
    uint32_t request = core_observer.request;
    if (request != core_observer.acknowledged) {
        if (request & 0x80000000u) {
            seal(2);
        } else {
            core_observer.start_boot = core_observer.boots;
            core_observer.elapsed_ticks = core_observer.samples = core_observer.events = 0;
            core_observer.dropped = core_observer.invalid_samples = 0;
            core_observer.max_lag = core_observer.max_lead = core_observer.config_mask = 0;
            core_observer.sealed_boot = core_observer.sealed_reset_flags = 0;
            core_observer.duration_ticks = DURATION;
            core_observer.threshold_ticks = THRESHOLD;
            core_observer.clock_hz = CLOCK_HZ;
            core_observer.state = 1;
            event(0u, 0, 0, 0, configuration());
        }
        core_observer.acknowledged = request;
        return;
    }
    if (core_observer.state != 1u) return;
    ++core_observer.samples;
    uint32_t mask = configuration();
    if (dt > 0x7FFFFFFFu || dc > 0x7FFFFFFFu) mask |= 32u;
    if (mask) {
        core_observer.config_mask |= mask;
        ++core_observer.invalid_samples;
        event(3u, dt, dc, 0, mask);
        seal(3);  /* Do not silently repair instrumentation during capture. */
        return;
    }
    uint32_t remaining = DURATION - core_observer.elapsed_ticks;
    core_observer.elapsed_ticks += dt < remaining ? dt : remaining;
    int32_t lag = (int32_t)(dt - dc);
    if (lag > 0 && (uint32_t)lag > core_observer.max_lag) core_observer.max_lag = (uint32_t)lag;
    if (lag < 0 && (uint32_t)(-lag) > core_observer.max_lead) core_observer.max_lead = (uint32_t)(-lag);
    if (lag >= (int32_t)THRESHOLD || lag <= -(int32_t)THRESHOLD) event(2u, dt, dc, lag, 0);
    if (core_observer.elapsed_ticks >= DURATION) seal(2);
}
