cmake_minimum_required(VERSION 3.15)
project(optimizer_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_BUILD_TYPE Release)

# --- pybind11: from pip or system ---
# pip's pybind11 provides CMake config via `python3 -m pybind11 --cmakedir`
execute_process(
  COMMAND python3 -m pybind11 --cmakedir
  OUTPUT_VARIABLE pybind11_DIR
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET
)
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
  find_package(pybind11 REQUIRED)
endif()

# --- OR-Tools: optional deep implementation ---
# Prefer ortools config; fallback to ORTools. NOT REQUIRED so stub can build without it.
find_package(ortools CONFIG QUIET)
if(ortools_FOUND)
  set(ORTOOLS_TARGET ortools::ortools)
  set(HAS_ORTOOLS 1)
else()
  find_package(ORTools CONFIG QUIET)
  if(ORTools_FOUND)
    set(ORTOOLS_TARGET ORTools::ortools)
    set(HAS_ORTOOLS 1)
  else()
    # also try pkg-config style
    find_library(ORTOOLS_LIB ortools QUIET)
    if(ORTOOLS_LIB)
      set(HAS_ORTOOLS 1)
    else()
      set(HAS_ORTOOLS 0)
      message(WARNING "OR-Tools not found — building pybind11 stub (Python fallback will be used). Install ortools dev package to enable C++ CP-SAT: apt install libortools-dev or pip install ortools")
    endif()
  endif()
endif()

pybind11_add_module(optimizer_cpp optimizer.cpp)

if(HAS_ORTOOLS)
  target_compile_definitions(optimizer_cpp PRIVATE HAS_ORTOOLS=1)
  if(DEFINED ORTOOLS_TARGET)
    target_link_libraries(optimizer_cpp PRIVATE ${ORTOOLS_TARGET})
  elseif(DEFINED ORTOOLS_LIB)
    target_link_libraries(optimizer_cpp PRIVATE ${ORTOOLS_LIB})
    find_path(ORTOOLS_INCLUDE ortools/sat/cp_model.h)
    if(ORTOOLS_INCLUDE)
      target_include_directories(optimizer_cpp PRIVATE ${ORTOOLS_INCLUDE})
    endif()
  endif()
else()
  target_compile_definitions(optimizer_cpp PRIVATE HAS_ORTOOLS=0)
endif()

target_compile_features(optimizer_cpp PRIVATE cxx_std_17)
target_compile_options(optimizer_cpp PRIVATE -O3 -Wall -Wextra -fvisibility=hidden)

# install to python package dir is handled by pip/CMake; also allow manual copy
install(TARGETS optimizer_cpp LIBRARY DESTINATION .)
