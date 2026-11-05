ENTRY(Reset_Handler)
MEMORY {
    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 128K
    RAM (rwx) : ORIGIN = 0x24000000, LENGTH = 512K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > FLASH
    .ARM.exidx : { *(.ARM.exidx*) } > FLASH
    .data : {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM AT> FLASH
    _sidata = LOADADDR(.data);
    .bss (NOLOAD) : {
        . = ALIGN(4);
        _sbss = .;
        KEEP(*(.bss.rtt))
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM
    .noinit (NOLOAD) : {
        . = ALIGN(4);
        *(.noinit*)
        . = ALIGN(4);
        _noinit_end = .;
    } > RAM
    ASSERT(_noinit_end < _estack - 4096, "Insufficient observer stack space")
    ASSERT(_ebss < _estack - 4096, "Insufficient stack space")
    ASSERT((_sidata % 4) == 0, "Unaligned data load image")
}
