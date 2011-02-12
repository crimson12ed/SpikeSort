from SpikeBeans import base, components
from nose.tools import ok_,raises
from nose import with_setup
import numpy as np
import json
import os

def setup():
    "set up test fixtures"

def teardown():
    "tear down test fixtures"
    base.features = base.FeatureBroker()
    
spike_dur = 5.
spike_amp = 100.
FS = 25E3
period = 100
n_spikes = 100
class DummySignalSource(base.Component):
    
    def __init__(self):
        
        self.period = period
        self.n_spikes = n_spikes
        super(DummySignalSource, self).__init__()
        
    def read_signal(self):
        
         #in milisecs
        n_pts = int(self.n_spikes*self.period/1000.*FS)
        sp_idx = (np.arange(1,self.n_spikes-1)*self.period*FS/1000).astype(int)
        spikes = np.zeros(n_pts)[np.newaxis,:]
        spikes[0,sp_idx]=spike_amp
        
        n = int(spike_dur/1000.*FS) #spike length
        spikes[0,:] = np.convolve(spikes[0,:], np.ones(n), 'full')[:n_pts]
        self.spt = (sp_idx+0.5)*1000./FS
        self.FS = FS
        spk_data ={"data":spikes,"n_contacts":1, "FS":FS}
        return spk_data
    
    def update(self):
        self.period = period*2
        self.n_spikes = n_spikes/2
        super(DummySignalSource, self).update()
    
    signal = property(read_signal)
    
class DummySpikeDetector(base.Component):
    def read_events(self):
        n_pts = int(n_spikes*period/1000.*FS)
        sp_idx = (np.arange(1,n_spikes-1)*period*FS/1000).astype(int)
        spt = (sp_idx+0.5)*1000./FS
        spt_data = {'data':spt}
        return spt_data
    
    events = property(read_events)

class DummyFeatureExtractor(base.Component):
    def read_features(self):
        n_feats=2
        features = np.vstack((np.zeros((n_spikes, n_feats)), 
                              np.ones((n_spikes, n_feats))
                            ))
        names = ["Fet{0}".format(i) for i in range(n_feats)]
        return {"data": features, "names":names}
    
    features = property(read_features)

class RandomFeatures(base.Component):
    def read_features(self):
        n_feats=2
        features = np.random.randn(n_spikes, n_feats)
        names = ["Fet{0}".format(i) for i in range(n_feats)]
        return {"data": features, "names":names}
    features = property(read_features)
        

@with_setup(setup, teardown)
def test_spike_detection():
    base.features.Provide("SignalSource", DummySignalSource())
    detector = components.SpikeDetector(thresh=50.)
    spt = detector.events
    
    source = base.features['SignalSource']
    ok_((np.abs(spt['data']-source.spt)<=1000./source.FS).all())


@with_setup(setup, teardown)
def test_spike_detection_update():
    base.features.Provide("SignalSource", DummySignalSource())
    detector = components.SpikeDetector(thresh=50.)
    spt = detector.events
    detector.thresh = spike_amp*2
    detector.update()
    spt_new = detector.events
    ok_(len(spt_new['data'])==0)

@with_setup(setup, teardown)
def test_bakerlab_event_source():
    file_descr = {"fspike":"{ses_id}{el_id}.sp",
                  "fspt":"{ses_id}{el_id}{cell_id}.spt",
                  "dirname":".",
                  "FS":5.E3,
                  "n_contacts":1}
    el_node = '/Test/s32test01/el1'
    cell_node = el_node+'/cell1'
    spt_data = np.random.randint(0,100, (10,))/200.
    conf_file = 'test.conf'
    spt_fname = "32test0111.spt"
    
    with open(conf_file, 'w') as fp:
         json.dump(file_descr, fp)
    
    (spt_data*200).astype(np.int32).tofile(spt_fname)
    
    src = components.BakerlabSource(conf_file, cell_node)
    
    spt_read = src.events
    
    os.unlink(conf_file)
    os.unlink(spt_fname)
    ok_((np.abs(spt_read['data']-spt_data)<=1/200.).all())

    
@with_setup(setup, teardown)
def test_bakerlab_signal_source():
    file_descr = {"fspike":"{ses_id}{el_id}.sp",
                  "fspt":"{ses_id}{el_id}{cell_id}.spt",
                  "dirname":".",
                  "FS":5.E3,
                  "n_contacts":1}
    el_node = '/Test/s32test01/el1'

    data = np.random.randint(-1000, 1000, (100,))
    conf_file = 'test.conf'
    fname = "32test011.sp"
    
    with open(conf_file, 'w') as fp:
         json.dump(file_descr, fp)
    
    data.astype(np.int16).tofile(fname)
    
    src = components.BakerlabSource(conf_file, el_node)
    
    sp_read = src.signal
    
    os.unlink(conf_file)
    os.unlink(fname)
    ok_((np.abs(sp_read['data']-data)<=1/200.).all())

@with_setup(setup, teardown)
def test_spike_extractor():
    base.features.Provide("SignalSource", DummySignalSource())
    base.features.Provide("SpikeMarkerSource", DummySpikeDetector())
    
    sp_waves = components.SpikeExtractor().spikes
    mean_wave = sp_waves['data'][:,:,0].mean(1) 
    time = sp_waves['time']
    true_spike = spike_amp*((time>=0) & (time<spike_dur))
    ok_(np.sum(np.abs(mean_wave-true_spike))<0.01*spike_amp)

@with_setup(setup, teardown)
def test_feature_extractor():
    base.features.Provide("SignalSource",      DummySignalSource())
    base.features.Provide("SpikeMarkerSource", DummySpikeDetector())
    base.features.Provide("SpikeSource",       components.SpikeExtractor())
    
    feat_comp = components.FeatureExtractor(normalize=False)
    feat_comp.add_feature("P2P")
    features = feat_comp.features
    
    ok_((features['data']==spike_amp).all())       

@with_setup(setup, teardown)
def test_cluster_component():
    base.features.Provide("FeatureSource", DummyFeatureExtractor())
    
    cluster_comp = components.ClusterAnalyzer("k_means", 2)
    labels = cluster_comp.read_labels()
    
    ok = (((labels[:n_spikes]==1).all() & (labels[n_spikes:]==2).all()) |
         ((labels[:n_spikes]==2).all() & (labels[n_spikes:]==1).all()))
    ok_(ok)

@with_setup(setup, teardown)
def test_cluster_component_relabel():
    base.features.Provide("FeatureSource", RandomFeatures())
    
    cluster_comp = components.ClusterAnalyzer("k_means", 5)
    labs = cluster_comp.labels
    cluster_comp.delete_cells(1,2,3,4)
    cluster_comp.relabel()
    
    labels = np.unique(cluster_comp.labels)
    labels.sort()
    
    ok_((labels==np.array([0,1])).all())


@with_setup(setup, teardown)
def test_pipeline_update():
    base.features.Provide("SignalSource",      DummySignalSource())
    base.features.Provide("SpikeMarkerSource", components.SpikeDetector(thresh=spike_amp/2.))
    base.features.Provide("SpikeSource",       components.SpikeExtractor())
    base.features.Provide("FeatureSource",     components.FeatureExtractor(normalize=False))
    base.features.Provide("ClusterAnalyzer",   components.ClusterAnalyzer("k_means", 2))
    
    base.features['FeatureSource'].add_feature("P2P")
    
    cl1 = base.features["ClusterAnalyzer"].labels
    base.features["SignalSource"].update()
    cl2 = base.features["ClusterAnalyzer"].labels
    ok_(~(len(cl1)==len(cl2)))
    