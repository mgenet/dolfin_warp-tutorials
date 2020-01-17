#coding=utf8

################################################################################
###                                                                          ###
### Created by Martin Genet, 2018-2019                                       ###
###                                                                          ###
### École Polytechnique, Palaiseau, France                                   ###
###                                                                          ###
################################################################################

# from builtins import *

import dolfin
import numpy
# import math

import dolfin_cm as dcm
from .Problem_Hyperelasticity import HyperelasticityProblem

################################################################################

class DoingTwoSubfuncPoroProblem(HyperelasticityProblem):



    def __init__(self,
            eta,
            kappa,
            w_contact = 1,
            type_porosity = 'mixed',
            p0 = 0):

        HyperelasticityProblem.__init__(self,w_incompressibility=False)
        self.eta                 = eta
        self.kappa               = kappa
        self.p0                  = p0
        self.w_contact           = w_contact
        self.inertia             = None
        self.porosity_init_val   = None
        self.porosity_init_field = None
        self.porosity_given      = None
        self.config_porosity     = None
        self.type_porosity       = type_porosity



    def add_porosity_subsol(self,
            degree):

        if self.porosity_init_val is not None:
            init_val = numpy.array([self.porosity_init_val])
        else:
            init_val = self.porosity_init_val

        if (degree == 0):
            self.add_scalar_subsol(
                name="Phi",
                family="DG",
                degree=0,
                init_val=init_val,
                init_field=self.porosity_init_field)
        else:
            self.add_scalar_subsol(
                name="Phi",
                family="CG",
                degree=degree,
                init_val=init_val,
                init_field=self.porosity_init_field)



    def get_Phi(self):

        Phi = 1 - (1 - self.Phi0) / self.kinematics.Je

        return Phi



    def set_internal_variables_porosity(self):

        self.Phi_fs = self.sfoi_fs

        self.Phi      = dolfin.Function(self.Phi_fs)
        self.Phi_old  = dolfin.Function(self.Phi_fs)

        self.add_foi(expr=self.Phi, fs=self.Phi_fs, name="Phi")

        self.Phi_test = dolfin.TestFunction(self.Phi_fs)
        self.Phi_tria = dolfin.TrialFunction(self.Phi_fs)

        Phi = self.get_Phi()

        self.a_expr = dolfin.inner(
            self.Phi_tria,
            self.Phi_test) * self.dV
        self.b_expr = dolfin.inner(
            Phi,
            self.Phi_test) * self.dV
        self.local_solver = dolfin.LocalSolver(
            self.a_expr,
            self.b_expr)
        self.local_solver.factorize()



    def update_internal_variables_at_t(self,
            t):

        self.Phi_old.vector()[:] = self.Phi.vector()[:]



    def update_internal_variables_after_solve(self,
            dt, t):

        self.local_solver.solve_local_rhs(self.Phi)



    def restore_old_value(self):

        self.Phi.vector()[:] = self.Phi_old.vector()[:]



    def set_subsols(self,
            U_degree=1):

        self.add_displacement_subsol(
            degree=U_degree)

        if self.type_porosity == 'mixed':
            self.add_porosity_subsol(
                degree=U_degree-1)



    def get_porosity_function_space(self):

        assert (len(self.subsols) > 1)
        return self.get_subsol_function_space(name="Phi")



    def set_Phi0_and_Phi(self,
            config_porosity='ref'):

        if self.config_porosity == 'ref':
            self.Phi0 = self.porosity_given
            self.Phi0pos = dolfin.conditional(dolfin.gt(self.Phi0,0), self.Phi0, 0)
            self.Phi0bin = dolfin.conditional(dolfin.gt(self.Phi0,0), 1, 0)
            if self.type_porosity == 'mixed':
                self.Phi  = self.subsols["Phi"].subfunc
            elif self.type_porosity == 'internal':
                self.set_internal_variables_porosity()
                self.inelastic_behaviors_internal += [self]
        elif self.config_porosity == 'deformed':
            assert(0)



    def set_kinematics(self):

        HyperelasticityProblem.set_kinematics(self)

        self.set_Phi0_and_Phi(self.config_porosity)
        self.kinematics.Js = self.kinematics.Je * (1 - self.Phi)



    def set_materials(self,
            elastic_behavior=None,
            elastic_behavior_dev=None,
            elastic_behavior_bulk=None,
            subdomain_id=None):

        self.set_kinematics()

        HyperelasticityProblem.set_materials(self,
                elastic_behavior=elastic_behavior,
                elastic_behavior_dev=elastic_behavior_dev,
                elastic_behavior_bulk=elastic_behavior_bulk,
                subdomain_id=subdomain_id)

        self.wbulk_behavior = dcm.SkeletonPoroBulkElasticMaterial(
                problem = self,
                kappa = self.kappa)
        self.wpor_behavior = dcm.WporPoroElasticMaterial(
                problem = self,
                eta = self.eta,
                type = 'exp')

        # self.wbulk_behavior = dcm.PorousMaterial(
        #     material=dcm.SkeletonPoroBulkElasticMaterial(
        #         problem = self,
        #         kappa = self.kappa),
        #     problem=self,
        #     porosity=self.porosity_given,
        #     config_porosity=self.config_porosity)
        # self.wpor_behavior = dcm.PorousMaterial(
        #     material=dcm.WporPoroElasticMaterial(
        #         problem = self,
        #         eta = self.eta,
        #         type = 'exp'),
        #     problem=self,
        #     porosity=self.porosity_given,
        #     config_porosity=self.config_porosity)



    def set_variational_formulation(self,
            normal_penalties=[],
            directional_penalties=[],
            surface_tensions=[],
            surface0_loadings=[],
            pressure0_loadings=[],
            volume0_loadings=[],
            surface_loadings=[],
            pressure_loadings=[],
            volume_loadings=[],
            dt=None):

        self.Pi = sum([subdomain.Psi * self.dV(subdomain.id) for subdomain in self.subdomains])
        # print (self.Pi)

        self.res_form = dolfin.derivative(
            self.Pi,
            self.sol_func,
            self.dsol_test);

        if self.inertia is not None:
            self.res_form += self.inertia / dt * dolfin.inner(
                    self.subsols["U"].subfunc,
                    self.subsols["U"].dsubtest) * self.dV

        for loading in pressure_loadings:
            T = dolfin.dot(
               -loading.val * self.mesh_normals,
                dolfin.inv(self.kinematics.Ft))
            self.res_form -= self.kinematics.Jt * dolfin.inner(
                T,
                self.subsols["U"].dsubtest) * loading.measure

        # self.res_form += dolfin.inner(
        #     self.dWbulkdJs_pos * self.kinematics.Je * self.kinematics.Ce_inv,
        #     dolfin.derivative(
        #             self.kinematics.Et,
        #             self.subsols["U"].subfunc,
        #             self.subsols["U"].dsubtest)) * self.dV

        self.res_form += self.wbulk_behavior.get_res_term(self.Phi0pos, w_U=1)

        if self.type_porosity == 'mixed':
            p0_loading_val = pressure0_loadings[0].val
            self.res_form += dolfin.inner(
                    p0_loading_val,
                    self.subsols["Phi"].dsubtest) * self.dV
            self.res_form += self.wbulk_behavior.get_res_term(self.Phi0, w_Phi=1)
            self.res_form += self.wpor_behavior.get_res_term()

        self.jac_form = dolfin.derivative(
            self.res_form,
            self.sol_func,
            self.dsol_tria)

        if self.type_porosity == 'internal':
            self.jac_form += self.wbulk_behavior.get_jac_term()



    def add_Phi0_qois(self):

        basename = "PHI0_"

        self.add_qoi(
            name=basename,
            expr=self.Phi0 / self.mesh_V0 * self.dV)



    def add_Phi_qois(self):

        basename = "PHI_"

        self.add_qoi(
            name=basename,
            expr=self.Phi / self.mesh_V0 * self.dV)



    def add_Js_qois(self):

        basename = "Js_"

        self.add_qoi(
            name=basename,
            expr=self.kinematics.Js / self.mesh_V0 * self.dV)



    def add_dWpordJs_qois(self):

        basename = "dWpordJs_"

        self.add_qoi(
            name=basename,
            # expr=0 / self.mesh_V0 * self.dV)
            expr=self.wpor_behavior.get_dWpordJs() / self.mesh_V0 * self.dV)
            # expr=self.dWpordJs / self.mesh_V0 * self.dV)



    def add_dWbulkdJs_qois(self):

        basename = "dWbulkdJs_"

        self.add_qoi(
            name=basename,
            # expr=0 / self.mesh_V0 * self.dV)
            expr=self.wbulk_behavior.get_dWbulkdJs(self.Phi0) / self.mesh_V0 * self.dV)
            # expr=self.dWbulkdJs / self.mesh_V0 * self.dV)



    def add_Phi0bin_qois(self):

        basename = "PHI0bin_"

        self.add_qoi(
            name=basename,
            expr=self.Phi0bin / self.mesh_V0 * self.dV)



    def add_Phi0pos_qois(self):

        basename = "PHI0pos_"

        self.add_qoi(
            name=basename,
            expr=self.Phi0pos / self.mesh_V0 * self.dV)



    def add_mnorm_qois(self):

        basename = "M_NORM"
        value = self.kinematics.Je * self.Phi - self.Phi0

        self.add_qoi(
            name=basename,
            expr=value / self.mesh_V0 * self.dV)
