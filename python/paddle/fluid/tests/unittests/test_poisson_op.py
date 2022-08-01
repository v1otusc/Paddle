#   Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import paddle
import numpy as np
from op_test import OpTest
import math
import os
from paddle.fluid.framework import _test_eager_guard

paddle.enable_static()
paddle.seed(100)


def output_hist(out, lam, a, b):
    prob = []
    bin = []
    for i in range(a, b + 1):
        prob.append((lam**i) * math.exp(-lam) / math.factorial(i))
        bin.append(i)
    bin.append(b + 0.1)

    hist, _ = np.histogram(out, bin)
    hist = hist.astype("float32")
    hist = hist / float(out.size)
    return hist, prob


class TestPoissonOp1(OpTest):

    def setUp(self):
        self.op_type = "poisson"
        self.config()

        self.attrs = {}
        self.inputs = {'X': np.full([2048, 1024], self.lam, dtype=self.dtype)}
        self.outputs = {'Out': np.ones([2048, 1024], dtype=self.dtype)}

    def config(self):
        self.lam = 10
        self.a = 5
        self.b = 15
        self.dtype = "float64"

    def verify_output(self, outs):
        hist, prob = output_hist(np.array(outs[0]), self.lam, self.a, self.b)
        self.assertTrue(np.allclose(hist, prob, rtol=0.01),
                        "actual: {}, expected: {}".format(hist, prob))

    def test_check_output(self):
        self.check_output_customized(self.verify_output)

    def test_check_grad_normal(self):
        self.check_grad(
            ['X'],
            'Out',
            user_defined_grads=[np.zeros([2048, 1024], dtype=self.dtype)],
            user_defined_grad_outputs=[
                np.random.rand(2048, 1024).astype(self.dtype)
            ])


class TestPoissonOp2(TestPoissonOp1):

    def config(self):
        self.lam = 5
        self.a = 1
        self.b = 8
        self.dtype = "float32"


class TestPoissonAPI(unittest.TestCase):

    def test_static(self):
        with paddle.static.program_guard(paddle.static.Program(),
                                         paddle.static.Program()):
            x_np = np.random.rand(10, 10)
            x = paddle.static.data(name="x", shape=[10, 10], dtype='float64')
            y = paddle.poisson(x)

            exe = paddle.static.Executor()
            y_np = exe.run(paddle.static.default_main_program(),
                           feed={"x": x_np},
                           fetch_list=[y])
            self.assertTrue(np.min(y_np) >= 0)

    def test_dygraph(self):
        with paddle.fluid.dygraph.base.guard():
            x = paddle.randn([10, 10], dtype='float32')
            y = paddle.poisson(x)
            self.assertTrue(np.min(y.numpy()) >= 0)

            with _test_eager_guard():
                x = paddle.randn([10, 10], dtype='float32')
                x.stop_gradient = False
                y = paddle.poisson(x)
                y.backward()
                self.assertTrue(np.min(y.numpy()) >= 0)
                self.assertTrue(np.array_equal(np.zeros_like(x), x.gradient()))

    def test_fixed_random_number(self):
        # Test GPU Fixed random number, which is generated by 'curandStatePhilox4_32_10_t'
        if not paddle.is_compiled_with_cuda():
            return

        if os.getenv("FLAGS_use_curand", None) in ('0', 'False', None):
            return

        print("Test Fixed Random number on GPU------>")
        paddle.disable_static()
        paddle.set_device('gpu')
        paddle.seed(2021)
        x = paddle.full([32, 3, 1024, 768], 10., dtype="float32")
        y = paddle.poisson(x)
        y_np = y.numpy()

        expect = [
            13., 13., 11., 8., 12., 6., 9., 15., 16., 6., 13., 12., 9., 15.,
            17., 8., 11., 16., 11., 10.
        ]
        self.assertTrue(np.array_equal(y_np[0, 0, 0, 0:20], expect))

        expect = [
            15., 7., 12., 8., 14., 10., 10., 11., 11., 11., 21., 6., 9., 13.,
            13., 11., 6., 9., 12., 12.
        ]
        self.assertTrue(np.array_equal(y_np[8, 1, 300, 200:220], expect))

        expect = [
            10., 15., 9., 6., 4., 13., 10., 10., 13., 12., 9., 7., 10., 14., 7.,
            10., 8., 5., 10., 14.
        ]
        self.assertTrue(np.array_equal(y_np[16, 1, 600, 400:420], expect))

        expect = [
            10., 9., 14., 12., 8., 9., 7., 8., 11., 10., 13., 8., 12., 9., 7.,
            8., 11., 11., 12., 5.
        ]
        self.assertTrue(np.array_equal(y_np[24, 2, 900, 600:620], expect))

        expect = [
            15., 5., 11., 13., 12., 12., 13., 16., 9., 9., 7., 9., 13., 11.,
            15., 6., 11., 9., 10., 10.
        ]
        self.assertTrue(np.array_equal(y_np[31, 2, 1023, 748:768], expect))

        x = paddle.full([16, 1024, 1024], 5., dtype="float32")
        y = paddle.poisson(x)
        y_np = y.numpy()
        expect = [
            4., 5., 2., 9., 8., 7., 4., 7., 4., 7., 6., 3., 10., 7., 5., 7., 2.,
            5., 5., 6.
        ]
        self.assertTrue(np.array_equal(y_np[0, 0, 100:120], expect))

        expect = [
            1., 4., 8., 11., 6., 5., 4., 4., 7., 4., 4., 7., 11., 6., 5., 3.,
            4., 6., 3., 3.
        ]
        self.assertTrue(np.array_equal(y_np[4, 300, 300:320], expect))

        expect = [
            7., 5., 4., 6., 8., 5., 6., 7., 7., 7., 3., 10., 5., 10., 4., 5.,
            8., 7., 5., 7.
        ]
        self.assertTrue(np.array_equal(y_np[8, 600, 600:620], expect))

        expect = [
            8., 6., 7., 4., 3., 0., 4., 6., 6., 4., 3., 10., 5., 1., 3., 8., 8.,
            2., 1., 4.
        ]
        self.assertTrue(np.array_equal(y_np[12, 900, 900:920], expect))

        expect = [
            2., 1., 14., 3., 6., 5., 2., 2., 6., 5., 7., 4., 8., 4., 8., 4., 5.,
            7., 1., 7.
        ]
        self.assertTrue(np.array_equal(y_np[15, 1023, 1000:1020], expect))
        paddle.enable_static()


if __name__ == "__main__":
    unittest.main()
