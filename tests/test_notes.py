import csv
import json
import os
import unittest
import uuid
import xml.etree.ElementTree as ET

from gmaps_list_export import parse_place, write_csv, write_geojson, write_gpx, write_json, write_kml


class NoteExportTests(unittest.TestCase):
    def setUp(self):
        self.out = os.path.abspath(".note-export-test-" + uuid.uuid4().hex)
        for extension in ("json", "csv", "geojson", "kml", "gpx"):
            self.addCleanup(self.remove_output, self.out + "." + extension)

    @staticmethod
    def remove_output(path):
        if os.path.exists(path):
            os.remove(path)

    def test_note_in_every_format(self):
        note = 'Meet at <gate> & bring "tickets" — café'
        raw = [None, [None, None, "Place label", None, "Street", [None, None, 12.5, 34.5],
                      ["first", "second"], "/g/place"], "Place", note]
        place = parse_place(raw)

        write_json([place], self.out)
        write_csv([place], self.out)
        write_geojson([place], self.out)
        write_kml([place], self.out, "List")
        write_gpx([place], self.out, "List")

        with open(self.out + ".json", encoding="utf-8") as output:
            self.assertEqual(json.load(output)[0]["note"], note)
        with open(self.out + ".csv", newline="", encoding="utf-8") as output:
            reader = csv.DictReader(output)
            self.assertEqual(reader.fieldnames,
                             ["name", "label", "address", "lat", "lng", "cid", "placeId", "note"])
            self.assertEqual(next(reader)["note"], note)
        with open(self.out + ".geojson", encoding="utf-8") as output:
            feature = json.load(output)["features"][0]
            self.assertEqual(feature["properties"]["note"], note)
        kml = ET.parse(self.out + ".kml")
        self.assertEqual(kml.findtext(".//{http://www.opengis.net/kml/2.2}Data[@name='note']/"
                                      "{http://www.opengis.net/kml/2.2}value"), note)
        gpx = ET.parse(self.out + ".gpx")
        self.assertEqual(gpx.findtext(".//{http://www.topografix.com/GPX/1/1}wpt/"
                                      "{http://www.topografix.com/GPX/1/1}cmt"), note)
        self.assertEqual(gpx.findtext(".//{http://www.topografix.com/GPX/1/1}wpt/"
                                      "{http://www.topografix.com/GPX/1/1}desc"), "Street")

    def test_empty_and_absent_notes(self):
        raw = [None, [None, None, "Label", None, "Street", [None, None, 12, 34]], "Place"]
        empty = parse_place(raw + [""])
        absent = parse_place(raw)
        self.assertEqual(empty["note"], "")
        self.assertIsNone(absent["note"])
        write_json([empty, absent], self.out)
        write_csv([empty, absent], self.out)
        write_geojson([empty, absent], self.out)
        write_kml([empty, absent], self.out, None)
        write_gpx([empty, absent], self.out, None)

        with open(self.out + ".json", encoding="utf-8") as output:
            self.assertEqual([p["note"] for p in json.load(output)], ["", None])
        with open(self.out + ".csv", newline="", encoding="utf-8") as output:
            self.assertEqual([p["note"] for p in csv.DictReader(output)], ["", ""])
        with open(self.out + ".geojson", encoding="utf-8") as output:
            self.assertEqual([f["properties"]["note"] for f in json.load(output)["features"]],
                             ["", None])
        self.assertEqual(len(ET.parse(self.out + ".kml").findall(
            ".//{http://www.opengis.net/kml/2.2}Data")), 0)
        self.assertEqual(len(ET.parse(self.out + ".gpx").findall(
            ".//{http://www.topografix.com/GPX/1/1}cmt")), 0)

    def test_note_without_coordinates_stays_in_tabular_formats(self):
        place = parse_place([None, [None, None, "Label"], "Place", "Saved note"])
        write_json([place], self.out)
        write_csv([place], self.out)
        write_geojson([place], self.out)
        write_kml([place], self.out, None)
        write_gpx([place], self.out, None)

        with open(self.out + ".json", encoding="utf-8") as output:
            self.assertEqual(json.load(output)[0]["note"], "Saved note")
        with open(self.out + ".csv", newline="", encoding="utf-8") as output:
            self.assertEqual(next(csv.DictReader(output))["note"], "Saved note")
        with open(self.out + ".geojson", encoding="utf-8") as output:
            self.assertEqual(json.load(output)["features"], [])
        self.assertEqual(ET.parse(self.out + ".kml").findall(
            ".//{http://www.opengis.net/kml/2.2}Placemark"), [])
        self.assertEqual(ET.parse(self.out + ".gpx").findall(
            ".//{http://www.topografix.com/GPX/1/1}wpt"), [])


if __name__ == "__main__":
    unittest.main()
