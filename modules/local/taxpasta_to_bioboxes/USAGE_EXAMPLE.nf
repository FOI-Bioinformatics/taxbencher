#!/usr/bin/env nextflow

/*
 * Example workflow showing how to use TAXPASTA_TO_BIOBOXES module
 */

nextflow.enable.dsl = 2

include { TAXPASTA_TO_BIOBOXES } from './main.nf'

workflow {

    // Example 1: Basic usage with minimal metadata
    ch_basic = Channel.of([
        [ id: 'sample1' ],
        file('sample1_taxpasta.tsv')
    ])

    TAXPASTA_TO_BIOBOXES(ch_basic)


    // Example 2: With custom parameters
    ch_custom = Channel.of([
        [
            id: 'sample2',
            sample_id: 'my_custom_sample',
            ranks: 'domain|phylum|class|order|family|genus|species',
            taxonomy_db: 'NCBI'
        ],
        file('sample2_taxpasta.tsv')
    ])

    TAXPASTA_TO_BIOBOXES(ch_custom)


    // Example 3: Processing multiple samples
    ch_multi = Channel.fromPath('results/taxpasta/*.tsv')
        .map { file ->
            def sample_id = file.baseName.replaceAll('_taxpasta', '')
            [
                [ id: sample_id ],
                file
            ]
        }

    TAXPASTA_TO_BIOBOXES(ch_multi)


    // Example 4: Integration with other processes
    // Assuming you have taxpasta output from another process:
    /*
    TAXPASTA_MERGE(ch_profiles)

    ch_for_conversion = TAXPASTA_MERGE.out.merged_profiles

    TAXPASTA_TO_BIOBOXES(ch_for_conversion)

    // Then pass to OPAL for evaluation
    OPAL(TAXPASTA_TO_BIOBOXES.out.bioboxes, ch_truth_data)
    */
}
