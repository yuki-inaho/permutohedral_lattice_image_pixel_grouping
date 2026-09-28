#include "permutohedral/core.hpp"
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <initializer_list>
#include <memory>
#include <stdexcept>
#include <utility>

namespace nb = nanobind;
using namespace nb::literals;
using Features = nb::ndarray<nb::numpy, const double, nb::ndim<2>, nb::c_contig, nb::device::cpu>;
using Labels = nb::ndarray<nb::numpy, const std::int32_t, nb::ndim<2>, nb::c_contig, nb::device::cpu>;
using Image = nb::ndarray<nb::numpy, const std::uint8_t, nb::shape<-1, -1, 3>, nb::c_contig, nb::device::cpu>;

namespace {
template<typename T> auto owned_array(std::vector<T>&& data, std::initializer_list<std::size_t> shape) {
    // The capsule owns the vector; arrays remain valid after the C++ call returns.
    auto storage = std::make_unique<std::vector<T>>(std::move(data));
    auto* pointer = storage.get();
    nb::capsule owner(pointer, [](void* p) noexcept { delete static_cast<std::vector<T>*>(p); });
    storage.release();
    return nb::ndarray<nb::numpy, T>(pointer->data(), shape, owner);
}
}
NB_MODULE(_native, module) {
    module.doc() = "Stateless C++17 permutohedral segmentation kernels";
    module.def("label_features", [](Features features) {
        if (features.shape(1) < 1 || features.shape(1) > 8)
            throw std::invalid_argument("Feature dimension must be between 1 and 8.");
        permutohedral::Partition output;
        { nb::gil_scoped_release release;
          output = permutohedral::label_features(features.data(), features.shape(0), int(features.shape(1))); }
        return nb::make_tuple(owned_array(std::move(output.labels), {features.shape(0)}), output.classes);
    }, "features"_a.noconvert());
    module.def("locate_simplices", [](Features features) {
        if (features.shape(1) < 1 || features.shape(1) > 8)
            throw std::invalid_argument("Feature dimension must be between 1 and 8.");
        permutohedral::Geometry output;
        const auto n = features.shape(0), d = features.shape(1) + 1;
        { nb::gil_scoped_release release;
          output = permutohedral::locate_simplices(features.data(), n, int(d - 1)); }
        return nb::make_tuple(owned_array(std::move(output.vertices), {n, d, d}),
                              owned_array(std::move(output.weights), {n, d}),
                              owned_array(std::move(output.elevated), {n, d}));
    }, "features"_a.noconvert());
    module.def("connected_components", [](Labels labels) {
        permutohedral::validate_shape(labels.shape(1), labels.shape(0));
        permutohedral::Partition output;
        { nb::gil_scoped_release release;
          output = permutohedral::connected_components(labels.data(), int(labels.shape(1)), int(labels.shape(0))); }
        return nb::make_tuple(owned_array(std::move(output.labels), {labels.shape(0), labels.shape(1)}), output.classes);
    }, "labels"_a.noconvert());
    module.def("merge_regions", [](Image image, Labels labels, int target, double compactness, double color_sigma) {
        permutohedral::validate_shape(image.shape(1), image.shape(0));
        if (labels.shape(0) != image.shape(0) || labels.shape(1) != image.shape(1))
            throw std::invalid_argument("Image and label shapes must match.");
        permutohedral::MergeResult output;
        { nb::gil_scoped_release release;
          output = permutohedral::merge_regions(
              {int(image.shape(1)), int(image.shape(0)), image.data()}, labels.data(),
              target, compactness, color_sigma); }
        return nb::make_tuple(owned_array(std::move(output.output.labels), {image.shape(0), image.shape(1)}),
                             output.output.classes, output.initial_components);
    }, "image"_a.noconvert(), "labels"_a.noconvert(), "target"_a,
       "compactness"_a = 0.3, "color_sigma"_a = 48.0);
}
