CXX ?= g++
CXXFLAGS ?= -O2 -Wall -Wextra -fPIC

.PHONY: all clean

all: librobot_uart.so

librobot_uart.so: robot_uart.cpp
	$(CXX) $(CXXFLAGS) -shared -o $@ $<

clean:
	rm -f librobot_uart.so
