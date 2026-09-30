"""Meaningful checks for aggregation, time shifts and rejected corrupt inputs."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from prepare_data import load_source,validate,derive

class DataPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables=load_source(ROOT/'data/source')
        cls.rules=json.loads((ROOT/'config/planning_rules.json').read_text())
        cls.derived,cls.configs=derive(cls.tables,cls.rules)

    def test_config_aggregation_preserves_each_order(self):
        mapping=self.derived['order_configuration_map']
        self.assertEqual(len(mapping),28000)
        self.assertEqual(len({r['order_product_id'] for r in mapping}),28000)
        self.assertEqual(self.configs,104)
        self.assertEqual(sum(r['demand_units'] for r in self.derived['demand_by_configuration']),28000)

    def test_individual_and_aggregated_component_demand(self):
        from collections import Counter,defaultdict
        bom=defaultdict(list)
        for r in self.tables['BOM']:bom[r['parent_product_id']].append(r)
        raw=Counter()
        for r in self.tables['demands']:
            for link in bom[r['product_id']]:raw[link['component_product_id'],r['period']]+=link['component_quantity']*r['demand_units']
        derived={(r['product_id'],r['due_period']):r['gross_requirement_units'] for r in self.derived['direct_component_gross_demand']}
        self.assertEqual(dict(raw),derived)

    def test_initial_flow_arrival_and_after_horizon_preservation(self):
        rows=self.derived['initial_arrivals']
        gear=[r for r in rows if r['from_node']=='gear-supplier_inv' and r['departure_period']==59]
        self.assertTrue(gear)
        self.assertTrue(all(r['arrival_period']==61 for r in gear))
        later=[r for r in rows if r['from_node']=='seat-supplier_trans' and r['departure_period']==60]
        self.assertTrue(later)
        self.assertTrue(all(r['arrival_period']==83 and r['horizon_status']=='after_horizon' for r in later))
        self.assertEqual(sum(r['flow_units'] for r in rows),sum(r['flow_units'] for r in self.tables['initial_flows']))

    def test_identity_bom_is_preserved_but_not_exploded(self):
        self.assertEqual(len(self.derived['identity_bom']),49)
        self.assertTrue(all(r['parent_product_id']!=r['component_product_id'] for r in self.derived['physical_bom']))
        battery={r['component_product_id']:r['component_quantity'] for r in self.derived['physical_bom'] if r['parent_product_id']=='BEV'}
        self.assertEqual(sorted(battery.values()),[4,6,10])

    def test_unknown_product_is_rejected(self):
        bad={**self.tables,'demands':copy.deepcopy(self.tables['demands'])}
        bad['demands'][0]['product_id']='DOES_NOT_EXIST'
        with self.assertRaises(ValueError):validate(bad,self.rules)

    def test_missing_capacity_day_is_rejected(self):
        bad={**self.tables,'capacity_at_arc':self.tables['capacity_at_arc'][1:]}
        with self.assertRaises(ValueError):validate(bad,self.rules)

    def test_supplier_schedule_gaps_are_not_filled(self):
        self.assertEqual(max(r['period'] for r in self.tables['max_flow_product_per_arc']),70)
        self.assertFalse(self.rules['solver_ready'])

if __name__=='__main__':unittest.main()
