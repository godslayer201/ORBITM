# -*- coding: utf-8 -*-

###############################################################################
###############################################################################
##                                                                           ##
##     _____ ___  ____  ___  _____       ______                              ##
##    |  _  | _ \|  _ \|_ _||_   _|     |      |                             ##
##    | |_| |   <|  _ < | |   | |       | \  / |  _                          ##
##    |_____|_|\_|____/|___|  |_|       |_|\/|_| |_|                         ##
##                                                     v 0.1                 ##
##                                                                           ##
##    FILE DESCRIPTION:                                                      ##
##                                                                           ##
##    This routine runs the orbit maintenance simulation following the       ##
##    decay model that I had simplified in 2018. The link to my paper is     ##
##    below. This routine does not require STK or any external libraries     ##
##    besides the basic imports you see below. It also runs at a fraction    ##
##    of a second, as compared to a full STK simulation with AstroGator,     ##
##    because it does not actually compute the orbit propagation, but it     ##
##    computes the nominal decay value based on the model, and solves only   ##
##    a two-body Kepler's equation, whereas STK does the propagation with    ##
##    remarkably high fidelity and thus is expected to be more accurate.     ##
##    In general, use this offline routine if you simply need a quick ball-  ##
##    park figure for your mission's Delta-V needs. Otherwise, use STK's.    ##
##                                                                           ##
##    Link: https://digitalcommons.usu.edu/smallsat/2018/all2018/364/        ##
##                                                                           ##
##    Written by Samuel Y. W. Low.                                           ##
##    First created 12-10-2020 10:18 AM (+8 GMT)                             ##
##    Last modified 25-11-2020 09:38 AM (+8 GMT)                             ##
##                                                                           ##
###############################################################################
###############################################################################



# Import basic utilities
import os
import math
import datetime
import comtypes
import numpy as np
import datetime
import matplotlib.pyplot as plt

""" #########################################################################

TO THE USER: DO NOT CHANGE PARAMETERS BELOW. CHANGE IT DIRECTLY IN THE GUI,
OR CHANGE IT MANUALLY IN THE CONFIG.TXT FILE!

######################################################################### """

def orbm_run_offline(tstart, tfinal,
                     sc_Cd, sc_area_d, sc_Ck, sc_area_a, sc_Cr, sc_area_r,
                     orb_a, orb_e, orb_i, orb_R, orb_w, orb_m,
                     maintenance_tolerance,
                     maintenance_margin,
                     maintenance_fro,
                     sc_mass, isp_min, isp_max):

    ###########################################################################
    ###########################################################################
    
    print("You are now running ORBITM's offline orbit maintenance. \n")
    
    # For thruster sizing, what range of Isp and fuel mass is needed?
    plot_Isp_Min = isp_min # s
    plot_Isp_Max = isp_max # s
    
    # As a rule of thumb, frozen repeat orbit maintenance generally takes about
    # 02x as much Delta-V per thrust as regular altitude maintenance due to the 
    # need for the thrusts to bring the SC above the reference to maintain the 
    # eastward-to-westward ground track shift.
    
    """ ######################################################################
    
    TO THE USER: DO NOT CHANGE ANY OF THE CODE BELOW, AS THE CODE IS HIGHLY
    DEPENDENT ON INTERFACING WITH THE RIGHT POINTERS TO THE RIGHT CLASSES.
    EDIT THE CODE BELOW, AT YOUR RISK, ONLY IF YOU KNOW WHAT YOU ARE DOING!
    
    ###################################################################### """
    
    ###########################################################################
    ###########################################################################
    
    # The program will now compute the total scenario time in seconds.
    
    months_dict = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4,
                   'May':5, 'Jun':6, 'Jul':7, 'Aug':8,
                   'Sep':9, 'Oct':10,'Nov':11,'Dec':12}
    
    def timestr2datetime(string):
        dt = datetime.datetime(int(string[6:10]),
                               int(months_dict[string[2:5]]),
                               int(string[0]),
                               int(string[11:13]),
                               int(string[14:16]),
                               int(string[17:19]))
        return dt
    
    # Read the start epoch string as a datetime object
    tstart_dt = timestr2datetime(tstart)
    
    # Read the final epoch string as a datetime object
    tfinal_dt = timestr2datetime(tfinal)
    
    # Read the time delta between start and final as a datetime-timedelta object
    tdelta_dt = tfinal_dt - tstart_dt
    
    # Compute the total scenario time in seconds
    tdelta = (tdelta_dt.days*86400) + tdelta_dt.seconds # int
    
    # Set the time step
    tstep = 600
    tstep_dt = datetime.timedelta(seconds=600)
    
    ###########################################################################
    ###########################################################################
    
    # The program will now compute what is the desired Delta-V per thrust
    # using a first order Taylor expansion of the Vis-Visa equation.
    
    GM = 398.6004415e12 # gravity constant x Earth mass (m**3/s**2)
    velocity = ((398.6004415e12)/(orb_a*1000))**0.5
    delta_v = (0.25*velocity*maintenance_tolerance)/(orb_a * 1000) # km/s
    
    ###########################################################################
    ###########################################################################
    
    from codes.orbitm_function_atmUS1976 import AtmosDensity
    from codes.orbitm_function_keplersolve import SolveKepEqn
    
    # Define all useful constants here
    J2CONST = 0.00108263 #J2 constant
    UNIGCONST = 6.67408e-11
    EARTHMASS = 5.97237e24 #in kg
    EARTHRAD = 6371.140 #in km
    EARTHRADEQT = 6378.140 #in km
    MUU = UNIGCONST*EARTHMASS # GM
    
    # Primary reference for drag analysis from publication:
        
    # Low, S. Y. W., &; Chia, Y. X. (2018). “Assessment of Orbit Maintenance
    # Strategies for Small Satellites”, 32nd Annual AIAA/USU Conference
    # on Small Satellites, Logan, Utah, Utah State University, USA. 
    
    ###########################################################################
    ###########################################################################
    
    # Define all the functions needed to compute the orbit decay.
    print("Setting up all functions for orbit propagation. \n")
    
    # Keplerian orbit period, with SMA as the semi-major axis (m)
    def OrbitPeriod(SMA):
        return 2*math.pi*math.sqrt((SMA**3)/MUU)
    
    # Orbit linear velocity, with R as radial distance from Earth Center (m)
    def Velocity(R,SMA):
        return math.sqrt(MUU*((2/R)-(1/SMA)))
    
    # Deceleration from drag, with R as radial distance from Earth Center (m)
    def DragAccel(R,SMA):
        Alt = R - (EARTHRADEQT*1000)
        AreaMassRatio = sc_area_d / sc_mass
        #SolRadConst = 4.5e-6
        #RefFactor = 0.25
        #SolarAreaMassRatio = sc_area_r / sc_mass
        V = Velocity(R,SMA)
        FDrag = 0.5*(AtmosDensity(Alt/1000))*sc_Cd*AreaMassRatio*(V**2)
        #FSolar = SolRadConst*(1+RefFactor)*(SolarAreaMassRatio)
        return FDrag
    
    # The decay rate of the altitude (dR/dt) in meters (see reference).
    def DecayRate(R, SMA):
        DragAcceleration = DragAccel(R,SMA)
        return (-1)*(DragAcceleration)*(OrbitPeriod(SMA))/(math.pi)
    
    # Define a function that computes the Delta-V needed for Hohmann transfer.
    def HohmannTransferDV(rd):
        R1 = rd
        if maintenance_fro == True:
            R2 = rd + (2*maintenance_tolerance*1000)
        else:
            R2 = rd + (maintenance_tolerance*1000)
        DV1 = math.sqrt(MUU/R1) * (math.sqrt((2*R2)/(R1+R2)) - 1)
        DV2 = math.sqrt(MUU/R2) * (1 - math.sqrt((2*R1)/(R1+R2)))
        totalDV = DV1+DV2
        Time_Elapsed = math.pi * math.sqrt(((R1+R2)**3)/(8*MUU))
        # Returns (Delta_V (m/s), Time_Elapsed (seconds))
        return totalDV, Time_Elapsed
    
    # Initialise all the parameters needed to do the run
    decay_alt = 0.0 # The decay amount in meters
    total_DV = 0.0 # Total Delta-V used (m/s)
    thrustcount = 0 # Counting the number of thrusts needed
    smaxis = orb_a * 1000 # Init the semi-major axis in meters
    meananom = np.deg2rad(orb_m) # Init the mean anomaly in radians
    
    # Initialise the lists for plotting
    sat_epochs, sat_altitude, sat_mean_sma = [], [], []
    
    # Now we need to setup the time sequence to run the simulation.
    # We will use a simple Keplerian propagator.
    
    print("Running mission control sequence now (this might take long). \n")
    
    deltaV_file = open("deltaV.txt",'w')
    while tstart_dt <= tfinal_dt:
        
        # Update the time step first.
        tstart_dt = tstart_dt + tstep_dt
        
        # First, we need to find the mean motion of the orbit at this instant.
        keplperiod = OrbitPeriod(smaxis)
        meanmotion = (2*np.pi) / keplperiod
        
        # Next, we can compute the mean anomaly at the next time step.
        meananom = (meananom + (meanmotion*tstep)) % np.pi
        
        # We can solve for the eccentric anomaly orb_E via Newton-Raphson
        # M = E - e*sin(E)
        eccnanom = SolveKepEqn(meananom, orb_e)
        
        # Now, we can substitute orb_E to find the satellite radial distance.
        rd = smaxis*(1-orb_e*np.cos(eccnanom))
        
        # Then, we can compute the decay rate (m/s), and apply it to the SMA.
        decay_rate = DecayRate(rd, smaxis)
        decay_alt = decay_rate * tstep
        smaxis += decay_alt
        
        # Append the data into the lists for plotting
        sat_epochs.append(tstart_dt)
        sat_altitude.append(rd/1000 - EARTHRADEQT)
        sat_mean_sma.append(smaxis/1000)
        
        # Now, we need to check if the orbit tolerance has been triggered.
        # If triggered, we will simply re-adjust the orbit as if a Hohmann
        # transfer had taken place.
        if smaxis < ((orb_a-maintenance_tolerance)*1000):
            DV, time_elapsed = HohmannTransferDV(rd)
            thrustcount += 1
            thrust_str = str(thrustcount) + "Maintain.Hohmann "
            thrust_str += str(tstart_dt) + " "
            thrust_str += str(DV) + " \n"
            deltaV_file.write(thrust_str)
            tstart_dt = tstart_dt+datetime.timedelta(seconds=int(time_elapsed))
            smaxis = orb_a*1000 # Reset the semi-major axis
            total_DV += DV
    
    # Close the Delta-V file
    deltaV_file.close()
    
    print("Mission successfully ran! Now extracting orbital data. \n")
    
    # Now, we need to start extracting relevant data.
    # Total impulse, inclusive of the margin of safety
    
    total_impulse = total_DV * sc_mass * maintenance_margin
    Isp = np.linspace(plot_Isp_Min, plot_Isp_Max, 500) # Isp axis, in (s)
    Mf = total_impulse / (Isp*9.81)
    
    print("The total impulse needed: " + str(total_impulse) + " \n")
    
    print("The total Delta-V (m/s) needed is " + str(total_DV) + " \n")
    
    # Plotting of altitudes
    plt.figure(1)
    plt.title("Plot of Satellite Altitude (km) Against Date-Time")
    plt.ylabel('Altitude (km)')
    plt.xlabel('Date-Time')
    plt.scatter(sat_epochs,sat_altitude,s=4,alpha=0.3)
    plt.grid()
    
    # Plotting of Kozai-Izsak mean semi-major axes
    plt.figure(2)
    plt.title("Plot of Keplerian Semimajor Axis (km) Against Date-Time")
    plt.ylabel('Keplerian Semimajor Axis (km)')
    plt.xlabel('Date-Time')
    plt.plot(sat_epochs,sat_mean_sma)
    plt.grid()
    
    # Thruster sizing profile of Isp Against Mass
    plt.figure(3)
    plt.title("Thruster Profile for Feasible ISPs (s) Against Fuel Mass (kg)")
    plt.ylabel('Mass of Fuel Required (kg)')
    plt.xlabel('Specific Impulse (s)')
    plt.plot(Isp, Mf)
    plt.grid()
    
    """ ######################################################################
    
    Notes: This part of the code reads the text file of all the shortlisted,
    thrusters and then plots them along the Isp-to-fuel-mass sizing chart.
    
    ###################################################################### """
    
    # Now we compare the mission propulsion requirements against thrusters.
    thr_file = open("thruster_shortlist.txt","r")
    
    thr_compn = []
    thr_model = []
    thr_isp_s = []
    thr_fuelm = []
    thr_force = []
    
    for line in thr_file:
        line_split = line.split()
        if line_split[0] != "COMPANY":
            thr_compn.append(str(line_split[0]))
            thr_model.append(str(line_split[1]))
            thr_isp_s.append(float(line_split[2]))
            thr_fuelm.append(float(line_split[3]))
            thr_force.append(str(line_split[4]))
    thr_file.close()
    
    plot_Isp_Min = 200.0 # N s
    plot_Isp_Max = 1250.0 # N s
    bwidth = (plot_Isp_Max - plot_Isp_Min)/50
    
    barchart = plt.bar(thr_isp_s, thr_fuelm, width = bwidth, color='green')
    
    # Then, we label each thruster accordingly.
    barcount = 0
    for rect in barchart:
        height = rect.get_height()
        bartext = thr_compn[barcount] + '\n'
        bartext = bartext + thr_model[barcount] + '\n'
        bartext = bartext + thr_force[barcount] + 'N'
        plt.text(rect.get_x() + rect.get_width()/2.0,
                 rect.get_height(),
                 bartext,
                 ha='center', va='bottom')
        barcount += 1
    
    return None
    # END OF SCRIPT
