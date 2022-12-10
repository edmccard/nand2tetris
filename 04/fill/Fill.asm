// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Fill.asm

// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen,
// i.e. writes "black" in every pixel;
// the screen should remain fully black as long as the key is pressed. 
// When no key is pressed, the program clears the screen, i.e. writes
// "white" in every pixel;
// the screen should remain fully clear as long as no key is pressed.

// Put your code here.
(RESET)
    @16383
    D=A
    @R0
    M=D
(LOOP)
    @R0
    M=M+1
    D=M
    @KBD
    D=D-A
    @RESET
    D;JGE
    @KBD
    D=M
    @WHITE
    D;JEQ
    @R0
    A=M
    M=-1
    @LOOP
    0;JMP
(WHITE)
    @R0
    A=M
    M=0
    @LOOP
    0;JMP
    
   
