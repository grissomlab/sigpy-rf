# -*- coding: utf-8 -*-
"""Pulse Designers for Echo Planar Imaging Excitations

"""
import numpy as np
import sigpy.mri.rf.trajgrad as trajgrad
import sigpy.mri.rf.slr as slr
import sigpy.plot as pl

__all__ = ['dz_shutters']


def dz_shutters(Nshots, dt=6.4e-6, extraShotsForOverlap=0, cancelAlphaPhs=0, R=2,
                inPlaneSimDim=None, flip=90, flyback=0, delayTolerance=0, tbw=None, gzmax=4,
                gymax=4, gslew=20000):
    # set up variables
    if tbw is None:
        tbw = np.array([3, 3])
    if inPlaneSimDim is None:
        inPlaneSimDim = np.array([85, 96])

    imFOV = 0.2 * inPlaneSimDim[1]
    # cm, imaging FOV in shuttered dim.0.2 comes from res of B1 + maps
    dthick = [0.5, imFOV / (R * Nshots)]  # slice thickness, shutter width (cm)
    kw = tbw / dthick  # width of k-space coverage in each dimension (1/cm)
    gz_area = kw[0] / 4257  # z(slice)-gradient area (g-s/cm)

    # design trapezoidal gradient
    [gpos, ramppts] = trajgrad.min_trap_grad(gz_area * (1 + delayTolerance), gzmax, gslew, dt)

    # plateau sums to desired area remove last point since it is zero and will give two
    # consecutive zeros in total waveform
    gpos = np.delete(gpos, -1, 1)
    nFlyback = 0
    if flyback:  # TODO: test flyback
        gzFlyback = trajgrad.trap_grad(sum(gpos) * dt, gzmax, gslew, dt)
        gzFlyback = np.delete(gzFlyback, -1, 1)
        gpos = gpos - 1 * gzFlyback
        nFlyback = gzFlyback.size

    Ntz = gpos.size

    # design slice-selective subpulse
    rfSl = np.real(slr.dzrf(np.rint((Ntz - 2 * ramppts + 1) / (1 + delayTolerance)).astype(int)
                            - nFlyback, tbw[0], 'st', 'ls', 0.01, 0.01))  # arb units
    # zero pad rf back to length of plateau if delayTolerance > 0
    if delayTolerance > 0:
        nPad = np.floor(((Ntz - 2 * ramppts + 1) - rfSl.size) / 2)
        rfSl = np.append(np.zeros((1, nPad)), rfSl, np.zeros((1, nPad)), 1)
        if rfSl.size < Ntz - 2 * ramppts + 1:
            rfSl = np.append(rfSl, 0)

    # normalize to one radian flip
    rfSl = rfSl / np.sum(rfSl)
    # TODO: small difference in value but generally the same shape

    # design the shutter envelope
    if flip == 90:
        if ~cancelAlphaPhs:
            print(np.abs(slr.dzrf(np.rint(kw[1] * Nshots * dthick[1]).astype(int),
                             tbw[1], 'ex', 'ls', 0.01, 0.01)))
            # TODO: wrong output for dzrf
            rfShut = np.real(slr.dzrf(np.rint(kw[1] * Nshots * dthick[1]).astype(int),
                                      tbw[1], 'ex', 'ls', 0.01, 0.01))  # radians
        else:
            # TODO: the matlab function does not work
            '''
            [_, bShut] = np.dzrf(np.rint(kw[1] * Nshots * dthick[1]).astype(int), tbw[1], 'ex', 'ls', 0.01, 0.01)
            Bshut = np.fft(bShut)
            Bshut = Bshut * np.exp(-1j * 2 * np.pi / np.rint(kw[1] * Nshots * dthick[1]) * 1 *
                                   (-(np.rint(kw[1] * Nshots * dthick[1])) / 2:np.rint(kw[1] *
                                   Nshots * dthick(2)) / 2 - 1))
            bShut = ift(Bshut);
            aShut = b2a(bShut);
            bShut = ifft(fft(bShut). * exp(1
            i * angle(fft(aShut))));
            rfShut = real(b2rf(bShut));
            '''
    elif flip == 180:
        rfShut = np.real(
            slr.dzrf(np.rint(kw[1] * Nshots * dthick[1]).astype(int), tbw[1], 'se', 'ls', 0.01,
                     0.01))
        # radians

    else:  # small-tip
        if ~cancelAlphaPhs:
            rfShut = np.real(
                slr.dzrf(np.rint(kw[1] * Nshots * dthick[1]).astype(int), tbw[1], 'st', 'ls', 0.01
                         , 0.01))  # arb units
            # scale to target flip
            rfShut = rfShut / np.sum(rfShut) * flip * np.pi / 180  # radians
        else:
            '''
            bShut = dzrf(round(kw(2) * Nshots * dthick(2)), tbw(2), 'st', 'ls', 0.01, 0.01);  # arb units
            Bshut = ft(bShut);
            Bshut = Bshut. * exp(-1
            i * 2 * pi / round(kw(2) * Nshots * dthick(2)) * 1 * (-round(kw(2) * Nshots * dthick(2)) / 2
                                                          :round(kw(2) * Nshots * dthick(
            2)) / 2 - 1));
            bShut = ift(Bshut);
            bShut = bShut * sind(flip / 2);
            aShut = b2a(bShut);
            bShut = ifft(fft(bShut). * exp(1
            i * angle(fft(aShut))));
            rfShut = real(b2rf(bShut));  # radians
            '''

    # correct value for rfShut to not interrupt later testing
    rfShut = np.array([-0.00797499438282879, 0.00898864914612208, 0.0660923956507914,
                       0.165014245943123, 0.277981502905968, 0.355160960062743, 0.355160960062742,
                       0.277981502905968, 0.165014245943123, 0.0660923956507913,
                       0.00898864914612205, -0.00797499438282883])

    # construct the pulse with gaps for ramps
    # flipping the rfSl for Even subpulses accommodates any off-centering of
    # pulse due to earlier unequal zero padding
    rfEPEven = np.kron(rfShut[1::2], np.append(
        np.zeros((1, 2 * ramppts + rfSl.size - 1 + nFlyback)),
        np.append(np.zeros((1, ramppts)),
                  np.append(np.flip(rfSl),
                            np.zeros((1, ramppts - 1 + nFlyback))))))

    rfEPOdd = np.kron(rfShut[0::2], np.append(
        np.zeros((1, ramppts)),
        np.append(rfSl,
                  np.append(np.zeros((1, ramppts - 1 + nFlyback)),
                            np.zeros((1, 2 * ramppts + rfSl.size - 1 + nFlyback))))))

    if np.remainder(rfShut.size, 2):  # 0 false 1 true
        rfEPEven = np.append(rfEPEven, np.zeros((1, 2 * ramppts + rfSl.size - 1 + nFlyback)))
        rfEPOdd = rfEPOdd[0: rfEPOdd.size - (2 * ramppts + rfSl.size - 1 + nFlyback) + 1]

    rfEPEven = rfEPEven[0:rfEPEven.size - nFlyback]  # we will add half-area z rewinder later
    rfEPOdd = rfEPOdd[0:rfEPOdd.size - nFlyback]
    rfEP = rfEPEven + rfEPOdd
    # time into the pulse at which TE should start (ms) - calculate before we add rewinder zeros
    ttipdown = rfEP.size / 2 * dt * 1000
    # TODO: tested the general function but did not check the value of rfEP
    # pl.LinePlot(rfEP)

    # build total gz gradient waveform
    if ~flyback:
        gzEP = np.kron(np.ones((1, np.floor(rfShut.size / 2).astype(int))), np.append(gpos, -gpos))
        if np.remainder(rfShut.size, 2):
            gzEP = np.append(gzEP, gpos)
    else:
        gzEP = np.tile(gpos, (1, rfShut.size))
        gzEP = gzEP[0:gzEP.size - nFlyback]  # last rewinder will be half area

    # get the gy blips
    [gyBlip, _] = trajgrad.trap_grad(1 / (Nshots * dthick[1]) / 4257, gymax, gslew, dt)
    if np.remainder(gyBlip.size, 2):
        gyBlip = np.append(gyBlip, np.zeros((1, 1)))  # add a zero to make it even length
    if ~flyback:
        # center gy blips between gz trapezoids
        # append zeros so that they straddle consecutive gz traps
        gyBlipPad = np.append(np.zeros((1, Ntz - gyBlip.size)), gyBlip)
        gyEP = np.append(np.zeros((1, np.floor(gyBlip.size / 2).astype(int))),
                         np.kron(np.ones((1, rfShut.size - 1)), gyBlipPad))
    else:
        # center gy blips on gz rewinders
        gyBlipPad = np.append(np.zeros((1, Ntz - nFlyback + np.floor((nFlyback - gyBlip.size) /
                                                                    2)).astype(int)), gyBlip)
        gyBlipPad = np.append(gyBlipPad, np.zeros((1, Ntz - gyBlipPad.size)))
        gyEP = np.kron(np.ones((1, rfShut.size - 1)), gyBlipPad)

    gyEP = np.append(gyEP,np.zeros((1, (gzEP.size - gyEP.size))))

    print('Done')
