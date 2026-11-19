#%%
import numpy as np
import netCDF4 as nc
from lxml import etree
import os
from scipy.interpolate import RegularGridInterpolator as RGI
from osgeo import gdal
from tqdm import tqdm

class lutWrapper:
    def __init__(self, parent, arr):
        self.parent = parent
        self.arr = arr
    
    @property
    def nc(self):
        return self.arr

    @property
    def data(self):
        return self.arr[:].data
    
    @property
    def upsampled(self):
        return self.parent.upsample(self.arr[:].data)

class bmLut:
    def __init__(self,lut,grdParams,isStack):
        self._lut = lut
        self._rg = grdParams[0] + grdParams[1]*np.arange(grdParams[2])
        self._az = grdParams[3] + grdParams[4]*np.arange(grdParams[5])

        if isStack:
            self._azLut = np.array((np.datetime64(self._lut.getncattr('referenceAzimuthTime')) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") + self._lut["relativeAzimuthTime"][:].data)
            self._rgLut = np.array(self._lut["slantRangeTime"])
        else:
            self._azLut = np.array((np.datetime64(self._lut.getncattr('referenceAzimuthTime')) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") + self._lut["relativeAzimuthTimeRGC"][:].data)
            self._rgLut = np.array(self._lut["slantRangeTimeRGC"])            

        try:
            self._azLutIono = np.array((np.datetime64(self._lut.getncattr('referenceAzimuthTime')) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") + self._lut["ionosphereRelativeAzimuthTime"][:].data)
            self._rgLutIono = np.array(self._lut["ionosphereSlantRangeTime"])
        except:
            self._rgLutIono = []
            self._azLutIono = []

    def get(self, group = None, variable = None):
        if (group == None) & (variable == None):
            arr = self._lut
            return lutWrapper(self,arr)

        elif variable == None:
            arr = self._lut[group]
            return lutWrapper(self,arr)

        elif group == None:
            arr = self._lut[variable]
            return lutWrapper(self,arr)
        
        else:    
            arr = self._lut[group][variable]
            return lutWrapper(self,arr)

    def upsample(self,arr):
        if len(self._rgLutIono) != 0:
            if arr.shape[0] == len(self._azLutIono):
                rgi = self._rgLutIono
                azi = self._azLutIono
            elif arr.shape[0] == len(self._azLut):
                rgi = self._rgLut
                azi = self._azLut
            else:
                raise RuntimeError("Lut dimensions doesn't match")
        else:
            if arr.shape[0] == len(self._azLut):
                rgi = self._rgLut
                azi = self._azLut
            else:
                raise RuntimeError("Lut dimensions doesn't match")
        
        AZ,RG = np.meshgrid(self._az,self._rg, indexing="ij")
        interp = RGI((azi,rgi), arr, bounds_error= False, method="linear")
        return interp((AZ,RG))       

def getAnots(self):
    parser = etree.XMLParser(remove_blank_text=True)
    primName = self.baseDirs[0] + "/annotation_primary/" + self.basenames[0][0:70].lower() + "_annot.xml"

    # Handles if image is L1a
    if os.path.exists(primName):
        self.annot_prim = etree.parse(primName,parser)
        for baseDir,basename in zip(self.baseDirs,self.basenames):
            coregName = baseDir + "/annotation_coregistered/" + basename[0:70].lower() + "_annot.xml"
            self.annot_coreg.append(etree.parse(coregName,parser))
            self._isStack = True
    else:
        # primName = self.baseDirs[0] + "/annotation/" + self.basenames[0][0:70].lower() + "_annot.xml"
        for baseDir,basename in zip(self.baseDirs,self.basenames):
            coregName = baseDir + "/annotation/" + basename[0:70].lower() + "_annot.xml"
            self.annot_coreg.append(etree.parse(coregName,parser))
        print("Warning! Annotation_coregistered not found, reading product(s) as L1a!")
        self._isStack = False

def getLuts(self):
    for baseDir,basename,annot in zip(self.baseDirs,self.basenames,self.annot_coreg):

        lutName = baseDir + "/annotation_coregistered/" + basename[0:70].lower() + "_lut.nc"
        if not os.path.exists(lutName):
            lutName = baseDir + "/annotation/" + basename[0:70].lower() + "_lut.nc"
        lutNC = nc.Dataset(lutName)
        
        # Extracts grid parameters
        r0 = float(annot.xpath("sarImage")[0].xpath("firstSampleSlantRangeTime")[0].text)
        dr = float(annot.xpath("sarImage")[0].xpath("rangeTimeInterval")[0].text)
        nr = int(annot.xpath("sarImage")[0].xpath("numberOfSamples")[0].text)
        a0 = (np.datetime64(annot.xpath("sarImage")[0].xpath("firstLineAzimuthTime")[0].text) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") # Seconds since com start
        da = float(annot.xpath("sarImage")[0].xpath("azimuthTimeInterval")[0].text)
        na = int(annot.xpath("sarImage")[0].xpath("numberOfLines")[0].text)

        grdParams = [
            r0,
            dr,
            nr,
            a0,
            da,
            na
        ]
        self.luts.append(bmLut(lutNC,grdParams,self._isStack))

class bmStack:
    """
        Python object for importing BIOMASS STA products

        Parameters
        ----------
        baseDirs : list (N)
            List containing the paths to the BIOMASS STA product directories

        Methods
        -------
        importSlcs()
            Imports SLC images
            
        Properties
        ----------
        baseDirs : list
            List containing the paths to the BIOMASS product directories
        annot_coreg : list (N)
            list of etree object containing the annotation xml file of the n'th product in the stack
        annot_primary : etree object
            etree object containing the annotation xml file of the 
        luts : list (N)
            List of bmLut objects
    """
    def __init__(self,baseDirs):
        c0 = 299792458
        fc = 435e6
        self.lamb = c0/fc

        self.baseDirs = baseDirs
        self.basenames = [os.path.basename(baseDir) for baseDir in baseDirs]
        self.annot_coreg = []
        self.annot_prim = []
        self.luts = []
        self._slcs = []

        self.Ntracks = len(baseDirs)

        getAnots(self)
        getLuts(self)

        # Exstracts master geometry
        if self._isStack:
            r0 = float(self.annot_prim.xpath("sarImage")[0].xpath("firstSampleSlantRangeTime")[0].text)
            dr = float(self.annot_prim.xpath("sarImage")[0].xpath("rangeTimeInterval")[0].text)
            nr = int(self.annot_prim.xpath("sarImage")[0].xpath("numberOfSamples")[0].text)
            t0 = (np.datetime64(self.annot_prim.xpath("sarImage")[0].xpath("firstLineAzimuthTime")[0].text) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") # Seconds since com start
            dt = float(self.annot_prim.xpath("sarImage")[0].xpath("azimuthTimeInterval")[0].text)
            da = float(self.annot_prim.xpath("sarImage")[0].xpath("azimuthPixelSpacing")[0].text)
            na = int(self.annot_prim.xpath("sarImage")[0].xpath("numberOfLines")[0].text)

            self.noDataValue = float(self.annot_prim.xpath("sarImage")[0].xpath("noDataValue")[0].text)

            self.rg = 1/2*c0*(r0 + dr*np.arange(nr))
            self.az = da*np.arange(na)
            self.t = t0 + dt*np.arange(na)
            self.nli = na
            self.nsa = nr
        else:
            r0 = [float(annot.xpath("sarImage")[0].xpath("firstSampleSlantRangeTime")[0].text) for annot in self.annot_coreg]
            dr = [float(annot.xpath("sarImage")[0].xpath("rangeTimeInterval")[0].text) for annot in self.annot_coreg]
            nr = [int(annot.xpath("sarImage")[0].xpath("numberOfSamples")[0].text) for annot in self.annot_coreg]
            t0 = [(np.datetime64(annot.xpath("sarImage")[0].xpath("firstLineAzimuthTime")[0].text) - np.datetime64("2025-05-22T09:47:44")) / np.timedelta64(1, "s") for annot in self.annot_coreg]
            dt = [float(annot.xpath("sarImage")[0].xpath("azimuthTimeInterval")[0].text) for annot in self.annot_coreg]
            da = [float(annot.xpath("sarImage")[0].xpath("azimuthPixelSpacing")[0].text) for annot in self.annot_coreg]
            na = [int(annot.xpath("sarImage")[0].xpath("numberOfLines")[0].text) for annot in self.annot_coreg]

            self.noDataValue = [float(annot.xpath("sarImage")[0].xpath("noDataValue")[0].text) for annot in self.annot_coreg]

            self.rg = [1/2*c0*(r0i + dri*np.arange(nri)) for r0i,dri,nri in zip(r0,dr,nr)]
            self.az = [dai*np.arange(nai) for dai,nai in zip(da,na)]
            self.t = [t0i + dti*np.arange(nai) for t0i,dti,nai in zip(t0,dt,na)]
            self.nli = na
            self.nsa = nr

    def importSlcs(self, terrain_flatten = True, swapaxes = True):
        for i,(baseDir,basename,lut) in enumerate(zip(tqdm(self.baseDirs,desc="Importing SLCs"),self.basenames,self.luts)):
            absFn = baseDir + "/measurement/" + basename[0:70].lower() + "_i_abs.tiff"
            phaseFn = baseDir + "/measurement/" + basename[0:70].lower() + "_i_phase.tiff"

            abs = gdal.Open(absFn).ReadAsArray()
            phase = gdal.Open(phaseFn).ReadAsArray()

            if self._isStack:
                abs[abs == self.noDataValue] = 0
                phase[phase == self.noDataValue] = 0
            else:
                abs[abs == self.noDataValue[i]] = 0
                phase[phase == self.noDataValue[i]] = 0

            
            if terrain_flatten:
                im = (abs * np.exp(1j*phase).astype(np.complex64)).astype(np.complex64)
                if self._isStack:
                    flatPhase = lut.get("coregistration","flatteningPhaseScreen").upsampled
                    self._slcs.append((im * np.exp(1j*flatPhase).astype(np.complex64)).astype(np.complex64))
                else:
                    self._slcs.append(im)
            else:    
                self._slcs.append((abs * np.exp(1j*phase).astype(np.complex64)).astype(np.complex64))

        if self._isStack:
            self._slcs = np.array(self._slcs, np.complex64)
        if swapaxes:
            if self._isStack:
                self._slcs = np.moveaxis(self._slcs,2,3)
            else:
                self._slcs = [slc.T for slc in self._slcs]

    @property
    def slcs(self):
        if len(self._slcs) == 0:
            raise RuntimeError("SLCs not imported")
        else:
            return self._slcs
    @slcs.setter
    def slcs(self,input):
        self._slcs = input   

#%% Usage example
if __name__ == "__main__":
    from glob import glob
    import matplotlib.pyplot as plt

    # Gets paths to BIOMASS STA products
    baseDirs = np.sort(glob("BIOMASS_STACK/BIO*"))
    print(baseDirs)

    # Sets up bmStack object
    stack = bmStack(baseDirs)
    # Usefull bmStack variables
    # stack.Ntracks : number of tracks
    # stack.rg : Slant range of the primary image [m]
    # stack.az : Azimuth of the primary image [m]
    # stack.nli : Number of azimuth lines
    # stack.nsa : Number of range samples

    # Imports SLCS without terrain flattening    
    # stack.importSlcs loads the BIOMASS SLCS into memory as a numpy array of size (N_tracks, N_pol, N_az, N_rg),
    # with N_pol = 4, and the polarisations ordered as (HH, HV, VH, VV).
    # terrain_flatten toggles whether or not terrain flattening is applied to the stack during import
    # swap_axes toggles whether or not the range and azimuth axes should be swaped.
    # When loaded, slcs can be retrieved through stack.slcs
    stack.importSlcs(terrain_flatten=False, swapaxes=False)

    # Displays polarimetric SLCs for in dB
    pols = ["HH","HV","VH","VV"]
    _,ax = plt.subplots(4,stack.Ntracks,layout="constrained",figsize=(9,12))
    dB_imgs = 20*np.log10(np.abs(stack.slcs[:,:,::9,::27]))
    for i in range(ax.shape[0]):
        for j in range(ax.shape[1]):
            p = ax[i,j].imshow(dB_imgs[j,i],cmap="gray",vmin=-27,vmax=10,extent=[1e-3*stack.rg[0],1e-3*stack.rg[-1],1e-3*stack.az[-1],1e-3*stack.az[0]])
    # [ax[0,j].set_title(os.path.basename(stack.baseDirs[j])) for j in range(stack.Ntracks)]
    [ax[i,0].set_ylabel(pols[i] + "\nAzimuth [km]") for i in range(len(pols))]
    [axi.set_xlabel("Range [km]") for axi in ax[-1,:]]
    [axi.set_xticklabels("") for axi in ax[:-1,:].flatten()]
    [axi.set_yticklabels("") for axi in ax[:,1:].flatten()]
    plt.colorbar(p,ax=ax[-1,:],label="Beta0 [dB]",pad=0.01,orientation="horizontal")
    plt.show()

    # Imports LUT variables
    # stack.lut.get() takes up to two arguments, the first a being netcdf group or variable, the second being a variable
    # in the group. stack.lut.get().nc returns the corresponding netcdf object
    # If the variable is an array, stack.lut.get().data returnes the variable as a numpy array, as it is stored in the LUT.
    # This array is downsampled w.r.t. the full image size
    # stack.lut.get().upsampled upsamples the array to the full image size and returns it as a numpy array
    #
    # LUT groups and variables can also be found in the BIOMASS l1C products description
    # Prints netCDF4 dataset for image 0
    stack.luts[0].get().nc

    # Prints variables for the group "coregistation"
    print(stack.luts[0].get("coregistration").nc.variables)

    # Gets upsampled terrain flattening phases
    flat_phase_upsamp = np.array([lut.get("coregistration","flatteningPhaseScreen").upsampled for lut in tqdm(stack.luts,desc="Upsampling flattening phases")])
    print(flat_phase_upsamp.shape)

