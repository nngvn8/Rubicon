cd ~/rubi-test-2/Rubicon/
./build/bin/computeUnit \
    -ip 127.0.0.1 \
    -port 23232 \
    -path data/binary/sf2 \
    -basedata bin \
    -worker 48 \
    -node 0 \
    -cxl_node 1
