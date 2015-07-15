__author__ = 'jreiter'

import logging
from utils.int_settings import NEG_UNKNOWN, POS_UNKNOWN
from phylogeny import ResolvedPhylogeny, CompatiblePhylogeny
from max_lh_phylogeny import MaxLHPhylogeny
from subclonal_phylogeny import SubclonalPhylogeny
import numpy as np
from collections import defaultdict
from itertools import cycle, chain
import scipy.cluster.hierarchy as sch
import matplotlib.pyplot as plt
import matplotlib as mpl
from copy import deepcopy
import math
from utils.statistics import calculate_present_pvalue, calculate_absent_pvalue
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch
from matplotlib import cm

# get logger for application
logger = logging.getLogger('treeomics')
rcParams['font.family'] = 'sans-serif'
rcParams['font.sans-serif'] = ['Arial']


def hinton(data, filename, row_labels=None, column_labels=None, displayed_mutations=None):
    """
    Draw Hinton diagram for visualizing mutation data of multiple samples.
    :param data: mutation data
    :param filename: path to the output file of the created figure (without ending), add pdf and png later
    :param row_labels: sample names
    :param column_labels: names of genes where the variant occurred
    :param displayed_mutations: depict only the given list of mutations in the table
    """

    # size and position settings
    height = 4
    width = 2
    y_spacing = 1
    label_x_pos = -2
    label_y_pos = 0

    # show all mutations in the table if no subset is given
    if displayed_mutations is None:
        displayed_mutations = [i for i in range(len(data))]

    x_length = ((-label_x_pos + 20) if row_labels is not None else 0) + (len(displayed_mutations) * width)
    y_length = len(data[0]) * (height+y_spacing) - y_spacing + (label_y_pos + 20 if column_labels is not None else 0)

    # create new figure
    plt.figure(figsize=(x_length / 20.0, y_length / 20.0), dpi=150)

    ax = plt.axes([0, 1, 1, 1])

    ax.patch.set_facecolor('white')
    ax.set_aspect('auto')
    ax.xaxis.set_major_locator(plt.NullLocator())
    ax.yaxis.set_major_locator(plt.NullLocator())

    # sort mutation table according to status
    priorities = [0 for _ in range(len(data))]
    for mut_idx in displayed_mutations:
        for sa_idx, maf in enumerate(data[mut_idx]):
            if maf > 0:     # mutation is present
                priorities[mut_idx] += 3 * (4 ** (len(data[mut_idx])-sa_idx-1))
            elif maf == POS_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                priorities[mut_idx] += 1 * (4 ** (len(data[mut_idx])-sa_idx-1))
            elif maf == NEG_UNKNOWN:
                priorities[mut_idx] += 1 * (4 ** (len(data[mut_idx])-sa_idx-1))
            else:
                priorities[mut_idx] += 0 * (4 ** (len(data[mut_idx])-sa_idx-1))

    edge_color = 'black'

    for x_pos, mut_idx in enumerate(sorted(displayed_mutations,
                                           key=lambda k: (-priorities[k],
                                                          column_labels[k] if column_labels is not None else 0))):

        for sa_idx, maf in enumerate(data[mut_idx]):
            if maf > 0:     # mutation is present
                color = 'blue'
            elif maf == POS_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                color = (0.9, 0.75, 0.75)
            elif maf == NEG_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                color = (0.9, 0.75, 0.75)
            else:
                color = (1.0, 0.3, 0.3)

            rect = plt.Rectangle([x_pos * width, (height+y_spacing) * (len(data[mut_idx]) - sa_idx - 1)], width, height,
                                 facecolor=color, edgecolor=edge_color)
            ax.add_patch(rect)

    if row_labels is not None:
        for sa_idx, row_name in enumerate(row_labels):
            ax.text(label_x_pos, (height+y_spacing) * (len(row_labels) - sa_idx - 1)+1, row_name.replace('_', ' '),
                    horizontalalignment='right', verticalalignment='bottom', fontsize=12)

    if column_labels is not None:
        for x_pos, mut_idx in enumerate(sorted(displayed_mutations,
                                               key=lambda k: (-priorities[k], column_labels[k]))):

            ax.text(x_pos * width+(width/2)+0.2, label_y_pos+(height+y_spacing) * (len(data[mut_idx])),
                    _format_gene_name(column_labels[mut_idx], max_length=12),
                    rotation='vertical', horizontalalignment='center', verticalalignment='bottom', fontsize=8)

    ax.autoscale_view()

    plt.savefig(filename+'.pdf', dpi=150, bbox_inches='tight', transparent=True)
    plt.savefig(filename+'.png', dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated mutation table plot: {}'.format(filename+'.pdf'))

    # plt.show(block=True)


def create_incompatible_mp_table(patient, filename, phylogeny, row_labels=None, column_labels=None):
    """
    Draw Hinton diagram for visualizing mutation data of multiple samples.
    :param patient: mutation data
    :param filename: path to the output file of the created figure (without ending), add pdf and png later
    :param phylogeny: data structure around the inferred phylogenetic tree
    :param row_labels: sample names
    :param column_labels: names of genes where the variant occurred
    """

    # size and position settings
    height = 4
    width = 1
    y_spacing = 1
    label_x_pos = -2
    label_y_pos = 0
    cb_width = 30.0

    if isinstance(phylogeny, CompatiblePhylogeny):
        displayed_mutations = [mut_idx for mut_idx in phylogeny.conflicting_mutations]
    elif isinstance(phylogeny, ResolvedPhylogeny):
        displayed_mutations = [mut_idx for mut_idx, samples in phylogeny.incompatible_positions.items()
                               if any(patient.data[mut_idx][sa_idx] >= 0 for sa_idx in samples)]
    elif isinstance(phylogeny, MaxLHPhylogeny):
        displayed_mutations = [mut_idx for mut_idx, samples in chain(phylogeny.false_positives.items(),
                                                                     phylogeny.false_negatives.items())]
    elif isinstance(phylogeny, SubclonalPhylogeny):
        logger.warning('Illustrative mutation table not yet implemented for subclonal detections.')
        return
    else:
        logger.error('Could not create illustrative mutation table of incompatible mutation patterns. ')
        logger.error('Phylogeny object is of wrong type! ')
        return

    x_length = ((-label_x_pos + 20) if row_labels is not None else 0) + (len(displayed_mutations) * width * 3)
    y_length = (len(patient.data[0]) * (height+y_spacing) - y_spacing
                + (label_y_pos + 20 if column_labels is not None else 0))

    x_length += cb_width

    # create new figure
    fig = plt.figure(figsize=(x_length / 20.0, y_length / 20.0), dpi=150)

    ax = plt.axes([0, 1, (x_length-cb_width)/x_length, 1])
    ax.axis('off')

    ax.patch.set_facecolor('white')
    ax.patch.set_edgecolor(None)
    # ax.set_aspect('auto')
    ax.xaxis.set_major_locator(plt.NullLocator())
    ax.yaxis.set_major_locator(plt.NullLocator())

    present_color = 'blue'
    absent_color = (1.0, 0.3, 0.3)
    unknown_color = (0.9, 0.75, 0.75)

    for x_pos, mut_idx in enumerate(sorted(displayed_mutations,
                                           key=lambda k: (column_labels[k].lower() if column_labels is not None else k))):

        for sa_idx, maf in enumerate(patient.data[mut_idx]):

            cov = float(patient.phred_coverage[patient.mut_keys[mut_idx]][patient.sample_names[sa_idx]])
            if cov > 0:
                raw_maf = (float(patient.mut_reads[patient.mut_keys[mut_idx]][patient.sample_names[sa_idx]]) / cov)
            else:
                raw_maf = 0.0

            if maf > 0:     # mutation is present
                class_color = present_color
            elif maf == POS_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                class_color = unknown_color
            elif maf == NEG_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                class_color = unknown_color
            else:
                class_color = absent_color

            maf_color = plt.cm.Blues(2.0 * raw_maf if raw_maf < 0.5 else 1.0)
            cov_color = plt.cm.Greens(math.log(cov, 10)/3 if 0 < cov < 1000 else 0.0 if cov <= 0.0 else 1.0)

            rect_maf = plt.Rectangle([(x_pos * width * 3) + 0,
                                      (height+y_spacing) * (len(patient.data[mut_idx]) - sa_idx - 1)],
                                     width, height, linewidth=0, facecolor=maf_color)
            rect_cov = plt.Rectangle([(x_pos * width * 3) + 1,
                                      (height+y_spacing) * (len(patient.data[mut_idx]) - sa_idx - 1)],
                                     width, height, linewidth=0, facecolor=cov_color)
            box = plt.Rectangle([(x_pos * width * 3), (height+y_spacing) * (len(patient.data[mut_idx]) - sa_idx - 1)],
                                width*2, height, linewidth=4, facecolor=None, edgecolor=class_color, clip_on=False)
            ax.add_patch(box)
            ax.add_patch(rect_maf)
            ax.add_patch(rect_cov)

            if isinstance(phylogeny, MaxLHPhylogeny):
                if mut_idx in phylogeny.false_positives.keys() and \
                        sa_idx in phylogeny.false_positives[mut_idx]:

                    af = plt.Rectangle([(x_pos * width * 3), (height+y_spacing) *
                                        (len(patient.data[mut_idx]) - sa_idx - 1)],
                                       width*2, height/2, facecolor=absent_color, linewidth=0)
                    ax.add_patch(af)

                elif mut_idx in phylogeny.false_negatives.keys() and sa_idx in phylogeny.false_negatives[mut_idx]:
                    af = plt.Rectangle([(x_pos * width * 3), (height+y_spacing) *
                                        (len(patient.data[mut_idx]) - sa_idx - 1)],
                                       width*2, height/2, facecolor=present_color, linewidth=0)
                    ax.add_patch(af)

    if row_labels is not None:
        for sa_idx, row_name in enumerate(row_labels):
            ax.text(label_x_pos, (height+y_spacing) * (len(row_labels) - sa_idx - 1)+1, row_name.replace('_', ' '),
                    horizontalalignment='right', verticalalignment='bottom', fontsize=12)

    if column_labels is not None:
        for x_pos, mut_idx in enumerate(sorted(displayed_mutations,
                                               key=lambda k: (column_labels[k].lower()))):

            ax.text(x_pos * width * 3 + width+0.1, label_y_pos+(height+y_spacing) * (len(patient.data[mut_idx])),
                    _format_gene_name(column_labels[mut_idx], max_length=12),
                    rotation='vertical', horizontalalignment='center', verticalalignment='bottom', fontsize=8)

    # draw colorbar legend to MAFs
    ax1 = fig.add_axes([(x_length-cb_width)/x_length+(cb_width/4/x_length), 1.05, 0.04, 0.9])
    # Set the colormap and norm to correspond to the data for which the colorbar will be used.
    cmap = cm.Blues
    norm = mpl.colors.Normalize(vmin=0, vmax=0.5)

    cb1 = mpl.colorbar.ColorbarBase(ax1, cmap=cmap, norm=norm, orientation='vertical')
    cb1.ax.tick_params(labelsize=8)
    cb1.set_label('VAF', labelpad=-cb_width*1.6)

    # draw colorbar legend to MAFs
    ax2 = fig.add_axes([(x_length-(cb_width/2))/x_length+(cb_width/4/x_length), 1.05, 0.04, 0.9])
    # Set the colormap and norm to correspond to the data for which the colorbar will be used.
    cmap = cm.Greens

    cb1 = mpl.colorbar.ColorbarBase(ax2, cmap=cmap, norm=mpl.colors.LogNorm(vmin=1, vmax=1000), orientation='vertical')
    cb1.ax.tick_params(labelsize=8)
    cb1.set_label('Coverage', labelpad=-cb_width*1.6)

    ax.autoscale_view()

    plt.savefig(filename+'.pdf', dpi=150, bbox_inches='tight', transparent=True)
    plt.savefig(filename+'.png', dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated illustrative mutation table plot of incompatible mutation patterns: {}'.format(
        filename+'.pdf'))

    return x_length, y_length


def boxplot(filename, patient):
    """
    Create box plot of the mutant allele frequencies in each sample
    :param filename: name of the output file
    :param patient: instance of the class patient
    """

    bp_fig, bp_ax = plt.subplots(figsize=(len(patient.sample_mafs)*0.56, 4))
    meanpointprops = dict(marker='o', markeredgecolor='black', markersize=4, markerfacecolor='none')

    data = []
    upper_labels = []    # number of mutations
    for sample_name in patient.sample_names:
        data.append(patient.sample_mafs[sample_name])
        upper_labels.append(len(patient.sample_mafs[sample_name]))

    bp = plt.boxplot(data, notch=0, showfliers=False, sym='+', vert=1, whis=1.5, meanprops=meanpointprops,
                     meanline=False, showmeans=True)

    bp_ax.set_ylim([0, 1.0])
    bp_ax.set_title(patient.name)
    bp_ax.set_xlabel('Samples')
    bp_ax.set_ylabel('Variant allele frequency')
    bp_ax.set_xticklabels([sa_n for sa_n in patient.sample_names], rotation=45)
    # caption = 'Mutant allele frequency (MAF) distribution in the DNA samples of {}. '.format(patient.name)
    # bp_fig.text(0, -0.2, caption,
    #                horizontalalignment='left', color='black', fontsize=10)
    for sa_idx, sample_name in enumerate(patient.sample_names):
        bp_ax.text(sa_idx+1, 0.93, len(patient.sample_mafs[sample_name]),
                   horizontalalignment='center', color='#707070', fontsize=9)
        bp_ax.text(sa_idx+1, 0.89, '{}x'.format(np.median(patient.sample_phred_coverages[sample_name])),
                   horizontalalignment='center', fontsize=8,
                   color=('#707070' if np.median(patient.sample_phred_coverages[sample_name]) >= 50 else 'red'))

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated boxplot for mutant allele frequencies {}'.format(filename))


def clustered_table(filename, patient, clusters, row_labels=None, column_labels=None, displayed_mutations=None):
    """
    Create a combined figure of the mutation table and the clustering results
    to visualize evolutionary conflicts.
    :param filename: path to the output file of the created figure
    :param patient: data
    :param clusters: matrix with 4 columns and n-1 rows stating which clusters were combined at each step
    :param row_labels: sample names
    :param column_labels: names of genes where the variant occurred
    :param displayed_mutations: depict only the given list of mutations in the table
    """

    # size and position settings
    height = 4
    width = 2
    y_spacing = 1
    label_x_pos = -2
    label_y_pos = 0

    row_label_rect_width = 21
    row_label_rect_height = 4

    # show all mutations in the table if no subset is given
    if displayed_mutations is None:
        displayed_mutations = [i for i in range(len(patient.data))]

    table_ax_width = -label_x_pos + (len(displayed_mutations) * width)
    dendrogram_ax_width = patient.n * width / 2.0
    x_length = ((-label_x_pos + 20) if row_labels is not None else 0) + table_ax_width + dendrogram_ax_width
    y_length = (len(patient.data[0]) * (height+y_spacing) - y_spacing
                + (label_y_pos + 20 if column_labels is not None else 0))

    fig = plt.figure(figsize=(x_length / 20.0, y_length / 20.0), dpi=150)

    # - - - - - - ADD DENDROGRAM - -  - - - - -
    ax_dg = plt.axes([1.0-(dendrogram_ax_width/float(x_length)), 1,
                      dendrogram_ax_width/float(x_length), 1], frameon=False)
    ax_dg.axis('off')

    den = sch.dendrogram(clusters, distance_sort='descending', orientation='left', labels=patient.sample_names,
                         color_threshold=len(patient.sample_names),
                         leaf_font_size=12, link_color_func=lambda k: 'black')

    # - - - - - ADD MUTATION TABLE - - - - -
    ax_hin = plt.axes([0, 1, 1.0-(dendrogram_ax_width/float(x_length)), 1])
    ax_hin.patch.set_facecolor('white')
    ax_hin.set_aspect('auto')
    ax_hin.xaxis.set_major_locator(plt.NullLocator())
    ax_hin.yaxis.set_major_locator(plt.NullLocator())

    # sort mutation table according to clustering and status
    priorities = [0 for _ in range(len(patient.data))]
    leave_ordering = deepcopy(den['leaves'])    # leave ordering based on the results of the clustering
    leave_ordering.reverse()
    for mut_idx in displayed_mutations:
        for i in range(len(patient.data[mut_idx])):

            sa_idx = int(leave_ordering[i])
            maf = patient.data[mut_idx][sa_idx]

            if maf > 0:     # mutation is present
                priorities[mut_idx] += 3 * (4 ** (len(patient.data[mut_idx])-i-1))
            elif maf == POS_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                priorities[mut_idx] += 1 * (4 ** (len(patient.data[mut_idx])-i-1))
            elif maf == NEG_UNKNOWN:
                priorities[mut_idx] += 1 * (4 ** (len(patient.data[mut_idx])-i-1))
            else:
                priorities[mut_idx] += 0 * (4 ** (len(patient.data[mut_idx])-i-1))

    edge_color = 'black'
    for x_pos, mut_idx in enumerate(sorted(displayed_mutations, key=lambda k: (-priorities[k],
                                                                               patient.gene_names[k]))):

        for i in range(len(patient.data[mut_idx])):

            sa_idx = leave_ordering[i]
            maf = patient.data[mut_idx][sa_idx]

            if maf > 0:     # mutation is present
                color = 'blue'
            elif maf == POS_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                color = (0.9, 0.75, 0.75)
            elif maf == NEG_UNKNOWN:
                # merge the two unknown categories when variants are displayed
                color = (0.9, 0.75, 0.75)
            else:
                color = (1.0, 0.3, 0.3)

            rect = plt.Rectangle([x_pos * width, (height+y_spacing) * (len(patient.data[mut_idx]) - i - 1)],
                                 width, height, facecolor=color, edgecolor=edge_color)
            ax_hin.add_patch(rect)

    # add sample name labels
    if row_labels is not None:
        for i, sa_idx in enumerate(reversed(den['leaves'])):
            ax_hin.text(label_x_pos, (height+y_spacing) * (len(row_labels) - i - 1)+0.5,
                        row_labels[sa_idx].replace('_', ' '),
                        horizontalalignment='right', verticalalignment='bottom', fontsize=12)

    # add mutation gene name labels
    if column_labels is not None:
        for x_pos, mut_idx in enumerate(sorted(displayed_mutations, key=lambda k: (-priorities[k],
                                                                                   patient.gene_names[k]))):

            ax_hin.text(x_pos * width+0.5, label_y_pos+(height+y_spacing) * (len(patient.data[mut_idx])),
                        _format_gene_name(patient.gene_names[mut_idx], max_length=12),
                        rotation='vertical', horizontalalignment='left', verticalalignment='bottom', fontsize=8)

    ax_dg.autoscale_view()
    ax_hin.autoscale_view()

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated combined mutation table and dendrogram {}'.format(filename))

    # plt.show(block=True)


def reads_plot(filename, patient):
    """
    Create scatter plot of the number of mutant reads over the coverage
    Each sample in a different color
    :param filename: path to the output file of the created figure
    :param patient: instance of class patient
    """
    # create scatter plot of the number of mutant reads over the coverage
    # each sample in a different color
    bp_fig, bp_ax = plt.subplots(figsize=(len(patient.sample_mafs)*0.56, 4))

    x_coverages = []
    y_mut_reads = []
    colors = []

    for mut_key in patient.mut_reads.keys():
        for sa_idx, sample_name in enumerate(patient.mut_reads[mut_key].keys(), 0):

            if patient.phred_coverage[mut_key][sample_name] > 0:
                x_coverages.append(patient.phred_coverage[mut_key][sample_name])
            else:
                x_coverages.append(1)
            if patient.mut_reads[mut_key][sample_name]:
                y_mut_reads.append(patient.mut_reads[mut_key][sample_name])
            else:
                y_mut_reads.append(1)

            colors.append(plt.cm.jet(1. * sa_idx / (patient.n - 1)))

    plt.scatter(x_coverages, y_mut_reads, c=colors, s=10, marker="x")

    bp_ax.set_xscale('log')
    bp_ax.set_xlim([1, 10000])
    bp_ax.set_yscale('log')
    bp_ax.set_ylim([1, 10000])
    bp_ax.set_xlabel('Coverage')
    bp_ax.set_ylabel('Variant reads')

    plt.show(block=False)
    x_labels = [item.get_text() for item in bp_ax.get_xticklabels()]
    # x_labels[1] = r'$\leq 10^0$'
    # x_labels[1] = '$\\mathdefault{\leq 10^{0}}$'
    x_labels[1] = '$\\mathdefault{\leq 1}$'
    bp_ax.set_xticklabels(x_labels)
    y_labels = [item.get_text() for item in bp_ax.get_yticklabels()]
    y_labels[1] = '$\\mathdefault{\leq 1}$'
    bp_ax.set_yticklabels(y_labels)

    y_pos = 5000
    for sa_idx, sample_name in enumerate(patient.sample_names):
        # bp_ax.text(1.3, y_pos, sample_name, horizontalalignment='left',
        #            color=plt.cm.spectral(1. * (sa_idx+1) / (patient.n+1)), fontsize=9)
        bp_ax.text(1.3, y_pos, sample_name[5:], horizontalalignment='left',
                   color=plt.cm.jet(1. * sa_idx / (patient.n - 1)), fontsize=9)
        y_pos /= 1.7

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated scatter plot about sequencing reads {}'.format(filename))

    # plt.show(block=True)


def p_value_present_plot(filename, patient, false_positive_rate):
    """
    Create plot with the p-values in each sample
    :param filename: path to the output file of the created figure
    :param patient: instance of class patient
    """
    bp_fig, bp_ax = plt.subplots(figsize=(5.6, 3))

    x_values = []
    y_values = []

    for mut_key in patient.mut_reads.keys():
        for sa_idx, sample_name in enumerate(patient.mut_reads[mut_key].keys(), 0):
            if patient.mut_reads[mut_key][sample_name] > 0:
                present_p_value = math.log(calculate_present_pvalue(patient.mut_reads[mut_key][sample_name],
                                                                    patient.phred_coverage[mut_key][sample_name],
                                                                    false_positive_rate), 10)
                x_values.append(present_p_value)
                y_values.append(patient.n-sa_idx)
                # colors.append(plt.cm.jet(1. * sa_idx / (patient.n - 1)))

    plt.scatter(x_values, y_values, c='black', s=10, marker="x")

    bp_ax.set_xlim([-5, 0])
    # bp_ax.set_xlabel('$\\mathdefault{\log_{10} \ (\mathrm{p-value})}$')
    bp_ax.set_xlabel(r'log$_{10}$ p-value')
    bp_ax.set_ylim([0.5, patient.n + 0.5])
    bp_ax.set_yticks(np.arange(1, patient.n+1, 1.0))
    y_labels = [item.get_text() for item in bp_ax.get_yticklabels()]

    for sa_idx, sample_name in enumerate(patient.sample_names):
        bp_ax.text(-5.6, patient.n-sa_idx-0.1, sample_name[5:], horizontalalignment='left',
                   color='black', fontsize=10)

    bp_ax.set_yticklabels(y_labels)

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated scatter plot about p-values of possibly present variants {}'.format(filename))


def p_value_absent_plot(filename, patient, min_maf):
    """
    Create plot with the p-values in each sample
    :param filename: path to the output file of the created figure
    :param patient: instance of class patient
    """
    # create plot with the p-values in each sample
    bp_fig, bp_ax = plt.subplots(figsize=(5.6, 3))

    x_values = []
    y_values = []
    # colors = []

    for mut_idx in range(len(patient.mut_keys)):
        mut_key = patient.mut_keys[mut_idx]
        for sa_idx, sample_name in enumerate(patient.sample_names):

            # don't show p-values for variants classified as present
            if patient.data[mut_idx][sa_idx] > 0:    # mutation has been classified as present
                continue

            absent_p_value = math.log(calculate_absent_pvalue(patient.mut_reads[mut_key][sample_name],
                                                              patient.phred_coverage[mut_key][sample_name], min_maf),
                                      10)
            x_values.append(absent_p_value)
            y_values.append(patient.n-sa_idx)
            # colors.append(plt.cm.jet(1. * sa_idx / (patient.n - 1)))

    plt.scatter(x_values, y_values, c='black', s=10, marker="x")

    bp_ax.set_xlim([-5, 0])
    #bp_ax.set_xlabel('$\\mathdefault{\log_{10} \ (\mathrm{p-value})}$')
    bp_ax.set_xlabel(r'log$_{10}$ p-value')
    bp_ax.set_ylim([0.5, patient.n + 0.5])
    bp_ax.set_yticks(np.arange(1, patient.n+1, 1.0))
    y_labels = [item.get_text() for item in bp_ax.get_yticklabels()]

    for sa_idx, sample_name in enumerate(patient.sample_names):
        bp_ax.text(-5.6, patient.n-sa_idx-0.1, sample_name.replace('_', ' '), horizontalalignment='left',
                   color='black', fontsize=10)

    bp_ax.set_yticklabels(y_labels)
    bp_ax.legend(loc='lower left', fontsize=10, frameon=True)

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated scatter plot about p-values of possibly absent variants {}'.format(filename))


def robustness_plot(filename, comp_node_frequencies):
    """
    Generate a plot about the reproducability of MPs when only a fraction of the variants are used
    :param filename: path to the output file of the created figure
    :param comp_node_frequencies: frequencies of the mutation patterns of how often they were reproduced with a
                                  a subset of the variants
    """

    fig, ax = plt.subplots(figsize=(5.6, 4))

    markers = cycle(['o', 's', 'v', '^', 'p', '*', 'D', 'x'])

    x_values = defaultdict(list)
    y_values = defaultdict(list)
    mp_ids = dict()

    # order legend according to most reproducible to least reproducible pattern
    for mp_id, (node, _) in enumerate(sorted(comp_node_frequencies[min(comp_node_frequencies.keys())].items(),
                                             key=lambda k: -k[1])):
            mp_ids[node] = mp_id

    last_fraction = None
    for sample_fraction in sorted(comp_node_frequencies.keys()):
        for node, _ in sorted(comp_node_frequencies[sample_fraction].items(), key=lambda k: -k[1]):

            x_values[mp_ids[node]].append(sample_fraction/100.0)
            y_values[mp_ids[node]].append(comp_node_frequencies[sample_fraction][node])

            if (last_fraction is not None and node in comp_node_frequencies[last_fraction]
                    and node in comp_node_frequencies[sample_fraction]):
                plt.plot([last_fraction/100.0, sample_fraction/100.0],
                         [comp_node_frequencies[last_fraction][node],
                          comp_node_frequencies[sample_fraction][node]],
                         'k:', lw=1,
                         color=plt.cm.jet(1. * mp_ids[node] / (len(comp_node_frequencies[sample_fraction].keys()) - 1)))

        last_fraction = sample_fraction

    plots = dict()
    for node, mp_id in sorted(mp_ids.items(), key=lambda k: k[1]):
        plots[mp_id] = plt.scatter(x_values[mp_id], y_values[mp_id],
                                   c=plt.cm.jet(1. * mp_id / (len(x_values.keys()) - 1)),
                                   s=15, marker=markers.next(), facecolors='none',
                                   edgecolors=plt.cm.jet(1. * mp_id / (len(x_values.keys()) - 1)), label='present')
    plt.legend(plots.values(),
               [','.join(str(s) for s in node) for node, _ in sorted(mp_ids.items(), key=lambda k: k[1])],
               scatterpoints=1, loc='lower right', fontsize=8)
    # plt.scatter(x_values, y_values, c='blue', s=15, marker="o", facecolors='none', edgecolors='blue', label='present')

    ax.set_xlim([0.0, 1.0])
    ax.set_xlabel('Used fraction of variants')
    ax.set_ylim([0.0, 1.0])
    ax.set_ylabel('Mutation pattern robustness')

    plt.savefig(filename, dpi=150, bbox_inches='tight', transparent=True)
    logger.info('Generated scatter plot about the mutation pattern robustness {}'.format(filename))


def _format_gene_name(gene_name, max_length=20):
    """
    Check the format of the gene name
    Replace apostrophes if necessary and shorten the name
    :param gene_name: name of the gene
    :param max_length: hard length limit
    :return: formatted gene name
    """

    # remove spaces and inverted comma
    gene_name = gene_name.replace(' ', '')
    gene_name = gene_name.replace('"', '')
    # shorten gene names if they are too long for the labeling
    if len(gene_name) > max_length-4 and gene_name.find(',', 6) != -1:
        logger.debug('Shorten too long gene name for circos labeling: {}'.format(gene_name))
        gene_name = gene_name[:gene_name.find(',', 6)]
    if len(gene_name) > max_length:
        # cut all names which are still longer
        gene_name = gene_name[:max_length]

    return gene_name