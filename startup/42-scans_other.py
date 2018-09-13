def test_test():
    yield from count([Andor], 2)
    h = db[-1]
    print(h.start['scan_id'])


def test_scan(exposure_time=0.1, out_x=-100, out_y=-100, num_bkg=10, note='', fn='/home/xf18id/tmp/tmp.h5', md=None):
    '''
    Take multiple images (Andor camera)

    Input:
    ------------
    exposure_time: float, exposure time for each image

    out_x: float(int), relative sample out position for zps.sx
    
    out_y: float(int), relative sampel out position for zps.sy

    num: int, number of images to take

    num_bkg: int, number of backgroud image to take

    fn: str, file name to save .h5 
    '''

    yield from mv(Andor.cam.acquire, 0)
    yield from mv(Andor.cam.image_mode, 0)
    yield from mv(Andor.cam.num_images, 1)
    yield from mv(Andor.cam.acquire_time, exposure_time)
    Andor.cam.acquire_period.put(exposure_time)    
    detectors = [Andor]
    y_ini = zps.sy.position
    y_out = y_ini + out_y
    x_ini = zps.sx.position
    x_out = x_ini + out_x
    _md = {'detectors': ['Andor'],
           'XEng': XEng.position,
           'plan_args': {'exposure_time': exposure_time,
                         'out_x': out_x,
                         'out_y': out_y,
                         'num_bkg': num_bkg,
                         'fn': f'{fn}',
                         'note': note if note else 'None',
                        },
           'plan_name': 'test_scan',
           'plan_pattern': 'linspace',
           'plan_pattern_module': 'numpy',
           'hints': {},
           'operator': 'FXI',
           'note': note if note else 'None',
           'motor_pos': wh_pos(print_on_screen=0),
            }
    _md.update(md or {})
    _md['hints'].setdefault('dimensions', [(('time',), 'primary')])

    @stage_decorator(list(detectors))
    @run_decorator(md=_md)
    def inner_scan():
        for i in range(num_bkg):
            yield from trigger_and_read(list(detectors))
        # taking out sample and take background image
        yield from mv(zps.sx, x_out, zps.sy, y_out)
        for i in range(num_bkg):
            yield from trigger_and_read(list(detectors))
        # close shutter, taking dark image
        yield from abs_set(shutter_close, 1, wait=True)
        yield from bps.sleep(2)
        yield from abs_set(shutter_close, 1, wait=True)
        yield from bps.sleep(2)
        for i in range(num_bkg):
            yield from trigger_and_read(list(detectors))
        yield from mv(zps.sx, x_ini, zps.sy, y_ini)
        yield from abs_set(shutter_open, 1, wait=True)
    uid = yield from inner_scan()
    txt = get_scan_parameter()
    insert_text(txt)
    print(txt)
#    print('loading test_scan and save file to current directory')
#    load_test_scan(db[-1])
    return uid


def z_scan(start=-0.03, stop=0.03, steps=5, out_x=-100, out_y=-100, chunk_size=10, exposure_time=0.1, fn='/home/xf18id/Documents/tmp/', note='', md=None):
    '''
    scan the zone-plate to find best focus
    use as:
    z_scan(start=-0.03, stop=0.03, steps=5, out_x=-100, out_y=-100, chunk_size=10, exposure_time=0.1, fn='/home/xf18id/Documents/tmp/z_scan.h5', note='', md=None)

    Input:
    ---------
    start: float, relative starting position of zp_z

    stop: float, relative stop position of zp_z

    steps: int, number of steps between [start, stop]

    out_x: float, relative amount to move sample out for zps.sx

    out_y: float, relative amount to move sample out for zps.sy

    chunk_size: int, number of images per each subscan (for Andor camera)

    exposure_time: float, exposure time for each image

    note: str, experiment notes 

    '''

    detectors=[Andor]
    motor = zp.z    
    z_ini = motor.position # zp.z intial position
    detectors = [Andor]
    y_ini = zps.sy.position # sample y position (initial)
    y_out = y_ini + out_y # sample y position (out-position)
    x_ini = zps.sx.position
    x_out = x_ini + out_x
    yield from mv(Andor.cam.acquire, 0)
    yield from mv(Andor.cam.image_mode, 0)
    yield from mv(Andor.cam.num_images, chunk_size)
    yield from mv(Andor.cam.acquire_time, exposure_time)
    Andor.cam.acquire_period.put(exposure_time)

    _md = {'detectors': [det.name for det in detectors],
           'motors': [motor.name],
           'XEng': XEng.position,
           'plan_args': {'start': start, 'stop': stop, 'steps': steps,
                         'out_x': out_x, 'out_y': out_y, 'chunk_size':chunk_size,                            
                         'exposure_time': exposure_time,
                         'fn': f'{fn}', 
                         'note': note if note else 'None'},
           'plan_name': 'z_scan',
           'plan_pattern': 'linspace',
           'plan_pattern_module': 'numpy',
           'hints': {},
           'operator': 'FXI',
           'motor_pos': wh_pos(print_on_screen=0),
            }
    _md.update(md or {})
    my_var = np.linspace(start, stop, steps)
    try:   dimensions = [(motor.hints['fields'], 'primary')]
    except (AttributeError, KeyError):  pass
    else:   _md['hints'].setdefault('dimensions', dimensions)
    @stage_decorator(list(detectors) + [motor])
    @run_decorator(md=_md)
    def inner_scan():
        yield from abs_set(shutter_open, 1, wait=True)
        for x in my_var:
            yield from mv(motor, x)
            yield from trigger_and_read(list(detectors)+[motor])
        # backgroud images
        yield from mv(zps.sx, x_out)
        yield from mv(zps.sy, y_out)
        yield from trigger_and_read(list(detectors)+[motor])
        # dark images
        yield from abs_set(shutter_close, 1, wait=True)
        yield from bps.sleep(1)
        yield from abs_set(shutter_close, 1)
        yield from trigger_and_read(list(detectors)+[motor])        
        # move back zone_plate and sample y 
        yield from mv(zps.sx, x_ini)
        yield from mv(zps.sy, y_ini)
        yield from mv(zp.z, z_ini)
        yield from abs_set(shutter_open, 1, wait=True)
    uid = yield from inner_scan()

    txt = get_scan_parameter()
    insert_text(txt)
    print(txt)
    print('loading z_scan and save file to current directory')
    load_z_scan(db[-1])
    return uid


#####################

'''
def cond_scan(detectors=[detA1], *, md=None):
    motor = clens.x

    _md = {'detectors': [det.name for det in detectors],
           'motors': [clens.x.name],

           'plan_args': {'detectors': list(map(repr, detectors)),
                         'motor': repr(motor),
                         },
           'plan_name': 'cond_scan',
           'hints': {},
           'operator': 'FXI',
           'motor_pos': wh_pos(),
            }
    _md.update(md or {})

    try:
        dimensions = [(motor.hints['fields'], 'primary')]
    except (AttributeError, KeyError):
        pass
    else:
        _md['hints'].setdefault('dimensions', dimensions)

    @stage_decorator(list(detectors))
    @run_decorator(md=_md)
    def cond_inner_scan():
        for x in range(6000, 7100, 100):
            for z1 in range(-800, 800, 20):
                for p in range(-600, 600, 10):
                    yield from mv_stage(clens.x, x)
                    yield from mv_stage(clens.z1, z1)
                    yield from mv_stage(clens.p, p)
                    yield from trigger_and_read(list(detectors))
    return (yield from cond_inner_scan())
'''


def load_cell_scan(pzt_cm_bender_pos_list, pbsl_y_pos_list, num, eng_start, eng_end, steps, delay_time=0.5):
    '''
    At every position in the pzt_cm_bender_pos_list, scan the pbsl.y_ctr under diffenent energies 
    Use as:
    load_cell_scan(pzt_cm_bender_pos_list, pbsl_y_pos_list, num, eng_start, eng_end, steps, delay_time=0.5)
    note: energies are in unit if keV
    '''

    txt1 = f'load_cell_scan(pzt_cm_bender_pos_list, pbsl_y_pos_list, num={num}, eng_start={eng_start}, eng_end={eng_end}, steps={steps}, delay_time={delay_time})'
    txt2 = f'pzt_cm_bender_pos_list = {pzt_cm_bender_pos_list}'
    txt3 = f'pbsl_y_pos_list = {pbsl_y_pos_list}'
    txt = '##' + txt1 + '\n' + txt2 + '\n' + txt3 + '\n  Consisting of:\n'
    insert_text(txt)

    check_eng_range([eng_start, eng_end])
    num_pbsl_pos = len(pbsl_y_pos_list)

    for bender_pos in pzt_cm_bender_pos_list:
        yield from mv(pzt_cm.setpos, bender_pos)
        yield from bps.sleep(1)
        load_cell_force = pzt_cm_loadcell.value
        fig = plt.figure()
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)
        for pbsl_pos in pbsl_y_pos_list:
            yield from mv(pbsl.y_ctr, pbsl_pos)
            for i in range(num):
                yield from eng_scan_delay(eng_start, eng_end, steps, delay_time=delay_time)
                h = db[-1]
                y0 = np.array(list(h.data(ic3.name)))
                y1 = np.array(list(h.data(ic4.name)))
                r = np.log(y0/y1)
                x = np.linspace(eng_start, eng_end, steps)
                ax1.plot(x, r, '.-')
                r_dif = np.array([0] + list(np.diff(r)))
                ax2.plot(x, r_dif, '.-')
        ax1.title.set_text('scan_id: {}-{}, ratio of: {}/{}'.format(h.start['scan_id']-num*num_pbsl_pos+1, h.start['scan_id'], ic3.name, ic4.name))
        ax2.title.set_text('load_cell: {}, bender_pos: {}'.format(load_cell_force, bender_pos))
        fig.subplots_adjust(hspace=.5)
        plt.show()
    txt_finish = '## "load_cell_scan()" finished'
    insert_text(txt_finish)

###########################
def ssa_scan_tm_bender(bender_pos_list, ssa_motor, ssa_start, ssa_end, ssa_steps):
    '''
    scanning ssa, with different pzt_tm_bender position
    '''
    txt1 = f'ssa_scan_tm_bender(bender_pos_list=bender_pos_list, ssa_motor={ssa_motor.name}, ssa_start={ssa_start}, ssa_end={ssa_end}, ssa_steps={ssa_steps})' 
    txt2 = f'bender_pos_list = {bender_pos_list}'
    txt = '## ' + txt1 + '\n' + txt2 + '\n  Consisting of:\n'
    insert_text(txt)    

    pzt_motor = pzt_tm.setpos
    x = np.linspace(ssa_start, ssa_end, ssa_steps)
    for bender_pos in bender_pos_list:
        yield from mv(pzt_motor, bender_pos)
        yield from bps.sleep(2)
        load_cell_force = pzt_tm_loadcell.value
        fig = plt.figure()
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312)
        ax3 = fig.add_subplot(313)
#        yield from scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps)
        yield from delay_scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps,  sleep_time=0.2, md=None)
        h = db[-1]
        y0 = np.array(list(h.data(ic3.name)))
        y1 = np.array(list(h.data(ic4.name)))
        y2 = np.array(list(h.data(Vout2.name)))
        ax1.plot(x, y0, '.-')
#            r_dif = np.array([0] + list(np.diff(r)))
        ax2.plot(x, y1, '.-')
        ax3.plot(x, y2, '.-')
        ax1.title.set_text('scan_id: {}, ic3'.format(h.start['scan_id']))
        ax2.title.set_text('ic4, load_cell: {}, bender_pos: {}'.format(load_cell_force, bender_pos))
        ax3.title.set_text('Vout2')
        fig.subplots_adjust(hspace=.5)
        plt.show()
    txt_finish='## "ssa_scan_tm_bender()" finished'
    insert_text(txt_finish)


def ssa_scan_tm_yaw(tm_yaw_pos_list, ssa_motor, ssa_start, ssa_end, ssa_steps):
    '''
    scanning ssa, with different tm.yaw position
    '''
    txt1 = f'ssa_scan_tm_yaw(tm_yaw_pos_list=tm_yaw_pos_list, ssa_motor={ssa_motor.name}, ssa_start={ssa-start}, ssa_end={ssa_end}, ssa_steps={ssa_steps})'
    txt2 = f'tm_yaw_pos_list = {tm_yaw_pos_list}'
    txt = '## ' + txt1 + '\n' + txt2 + '\n  Consisting of:\n'
    insert_text(txt)
    motor = tm.yaw
    x = np.linspace(ssa_start, ssa_end, ssa_steps)
    for tm_yaw_pos in tm_yaw_pos_list:
        yield from mv(motor, tm_yaw_pos)
        yield from bps.sleep(2)
        load_cell_force = pzt_tm_loadcell.value
        fig = plt.figure()
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312)
        ax3 = fig.add_subplot(313)
#        yield from scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps)
        yield from delay_scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps, sleep_time=1.2, md=None)
        h = db[-1]
        y0 = np.array(list(h.data(ic3.name)))
        y1 = np.array(list(h.data(ic4.name)))
        y2 = np.array(list(h.data(Vout2.name)))
        ax1.plot(x, y0, '.-')
#            r_dif = np.array([0] + list(np.diff(r)))
        ax2.plot(x, y1, '.-')
        ax3.plot(x, y2, '.-')
        ax1.title.set_text('scan_id: {}, ic3'.format(h.start['scan_id']))
        ax2.title.set_text('ic4, load_cell: {}'.format(load_cell_force))
        ax3.title.set_text('Vout2, tm_yaw = {}'.format(tm_yaw_pos))
        fig.subplots_adjust(hspace=.5)
        plt.show()
    txt_finish='## "ssa_scan_tm_yaw()" finished'
    insert_text(txt_finish)


def ssa_scan_pbsl_x_gap(pbsl_x_gap_list, ssa_motor, ssa_start, ssa_end, ssa_steps):
    '''
    scanning ssa, with different pbsl.x_gap position
    '''

    txt1 = f'ssa_scan_pbsl_x_gap(pbsl_x_gap_list=pbsl_x_gap_list, ssa_motor={ssa_motor.name}, ssa_start={ssa-start}, ssa_end={ssa_end}, ssa_steps={ssa_steps})'
    txt2 = f'pbsl_x_gap_list = {pbsl_x_gap_list}'
    txt = '## ' + txt1 + '\n' + txt2 + '\n  Consisting of:\n'
    insert_text(txt)
    
    motor = pbsl.x_gap
    x = np.linspace(ssa_start, ssa_end, ssa_steps)
    for pbsl_x_gap in pbsl_x_gap_list:
        yield from mv(motor, pbsl_x_gap)
        yield from bps.sleep(2)
        load_cell_force = pzt_tm_loadcell.value
        fig = plt.figure()
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312)
        ax3 = fig.add_subplot(313)
#        yield from scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps)
        yield from delay_scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps,  sleep_time=1.2, md=None)
        h = db[-1]
        y0 = np.array(list(h.data(ic3.name)))
        y1 = np.array(list(h.data(ic4.name)))
        y2 = np.array(list(h.data(Vout2.name)))
        ax1.plot(x, y0, '.-')
#            r_dif = np.array([0] + list(np.diff(r)))
        ax2.plot(x, y1, '.-')
        ax3.plot(x, y2, '.-')
        ax1.title.set_text('scan_id: {}, ic3'.format(h.start['scan_id']))
        ax2.title.set_text('ic4, load_cell: {}'.format(load_cell_force))
        ax3.title.set_text('Vout2, pbsl_x_gap = {}'.format(pbsl_x_gap))
        fig.subplots_adjust(hspace=.5)
        plt.show()
    txt_finish='## "ssa_scan_pbsl_x_gap()" finished'
    insert_text(txt_finish)


def ssa_scan_pbsl_y_gap(pbsl_y_gap_list, ssa_motor, ssa_start, ssa_end, ssa_steps):
    '''
    scanning ssa, with different pbsl.y_gap position
    '''
    txt1 = f'ssa_scan_pbsl_y_gap(pbsl_y_gap_list=pbsl_y_gap_list, ssa_motor={ssa_motor.name}, ssa_start={ssa-start}, ssa_end={ssa_end}, ssa_steps={ssa_steps})'
    txt2 = f'pbsl_y_gap_list = {pbsl_y_gap_list}'
    txt = '## ' + txt1 + '\n' + txt2 + '\n  Consisting of:\n'
    insert_text(txt)
    
    motor = pbsl.y_gap
    x = np.linspace(ssa_start, ssa_end, ssa_steps)
    for pbsl_y_gap in pbsl_y_gap_list:
        yield from mv(motor, pbsl_y_gap)
        yield from bps.sleep(2)
        load_cell_force = pzt_tm_loadcell.value
        fig = plt.figure()
        ax1 = fig.add_subplot(311)
        ax2 = fig.add_subplot(312)
        ax3 = fig.add_subplot(313)
#        yield from scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps)
        yield from delay_scan([ic3, ic4, Vout2], ssa_motor, ssa_start, ssa_end, ssa_steps,  sleep_time=1.2, md=None)
        h = db[-1]
        y0 = np.array(list(h.data(ic3.name)))
        y1 = np.array(list(h.data(ic4.name)))
        y2 = np.array(list(h.data(Vout2.name)))
        ax1.plot(x, y0, '.-')
#            r_dif = np.array([0] + list(np.diff(r)))
        ax2.plot(x, y1, '.-')
        ax3.plot(x, y2, '.-')
        ax1.title.set_text('scan_id: {}, ic3'.format(h.start['scan_id']))
        ax2.title.set_text('ic4, load_cell: {}'.format(load_cell_force))
        ax3.title.set_text('Vout2, pbsl_y_gap = {}'.format(pbsl_y_gap))
        fig.subplots_adjust(hspace=.5)
        plt.show()
    txt_finish='## "ssa_scan_pbsl_y_gap()" finished'
    insert_text(txt_finish)


def repeat_scan(detectors, motor, start, stop, steps, num=1, sleep_time=1.2):
    det = [det.name for det in detectors]
    det_name = ''
    for i in range(len(det)):
        det_name += det[i]
        det_name += ', '
    det_name = '[' + det_name[:-2] + ' ]'
    txt1 = 'repeat_scan(detectors=detectors, motor={motor.name}, start={start}, stop={stop}, steps={steps}, num={num}, sleep_time={sleep_time})'
    txt2 = 'detectors={det_name}'
    txt = txt1 + '\n' + txt2 + '\n  Consisting of:\n'
    print(txt)
    for i in range(num):
        yield from delay_scan(detectors, motor, start, stop, steps,  sleep_time=1.2)






