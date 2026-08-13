# Install all dependencies
pip install -r ext/SIMDOperators/tools/tslgen/requirements.txt # python dependencies
curl  -LsSf https://astral.sh/uv/install.sh | sh # uv
bash generate_python_proto.sh # generate proto files

# Generate the data
yes | cp ./setup.sh ../../data
cd ../../data
bash setup.sh

# Go to project root
cd ../..

# Build the project
yes | cp ./deployment-scripts/xps9370/CMakeLists.txt .
rm -rf build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$(which python)"
cmake --build build -j$(nproc)