import json

from qgis.gui import QgisInterface
#from qgis.utils import iface

from qgis.core import QgsApplication
from PyQt5.QtCore import QUrl, QByteArray, QCoreApplication
from PyQt5.QtNetwork import QNetworkRequest
from qgis.core import QgsNetworkAccessManager


def _run():
    # Zorg ervoor dat QGIS correct is geïnitialiseerd
    #QgsApplication.setPrefixPath("/path/to/qgis/installation", True)
    # qgs = QgsApplication([], False)
    # qgs.initQgis()

    # URL van de webservice
    url = QUrl("http://brdr-grb.aph9bzcjg6gxbtfk.westeurope.azurecontainer.io/actualiser")

    body_json = {
  "featurecollection": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "id": "2",
        "properties":{},
        "geometry": {
          "type": "MultiPolygon",
          "coordinates": [
            [
              [
                [
                  174111.5042,
                  179153.924300000013318
                ],
                [
                  174110.0614,
                  179154.109399999986636
                ],
                [
                  174068.867,
                  179159.3947
                ],
                [
                  174068.86610000001383,
                  179159.426199999987148
                ],
                [
                  174068.8626,
                  179159.557299999985844
                ],
                [
                  174073.7483,
                  179188.9357
                ],
                [
                  174120.4387,
                  179180.3235
                ],
                [
                  174116.133299999986775,
                  179157.20250000001397
                ],
                [
                  174111.549009999987902,
                  179153.956007
                ],
                [
                  174111.5042,
                  179153.924300000013318
                ]
              ]
            ]
          ]
        }
      }
    ]
  },
  "params": {
    "crs": "EPSG:31370",
    "grb_type": "adp",
    "prediction_strategy": "prefer_full"
  }
}
    body_json_byte = json.dumps(body_json).encode('utf-8')



    # Gegevens die je wilt verzenden
    data = QByteArray(body_json_byte)

    # # URL van de webservice
    # url = QUrl("https://jsonplaceholder.typicode.com/posts")
    #
    # # Gegevens die je wilt verzenden
    # data = QByteArray(b'{"title": "foo", "body": "bar", "userId": 1}')

    # Headers (optioneel)
    request = QNetworkRequest(url)
    request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
    #request.setRawHeader(b"Authorization", b"Bearer YOUR_ACCESS_TOKEN")

    # Maak een Network Access Manager
    network_manager = QgsNetworkAccessManager.instance()

    # Verstuur het POST-verzoek
    reply = network_manager.post(request, data)

    # Callback functie om de respons te verwerken
    def handle_response():
        if reply.error() == reply.NoError:
            print("Succes:", reply.readAll().data().decode())
        else:
            print("Fout:", reply.error(), reply.errorString())

    # Verbind de callback functie met het finished signaal
    reply.finished.connect(handle_response)

    # Zorg ervoor dat de applicatie blijft draaien totdat het verzoek is voltooid
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])

    app.exec_()

    # Sluit QGIS af
    #qgs.exitQgis()


if __name__ == "__main__":
    # workfolder = get_workfolder("notwritable/", "testrun", False)
    # print(workfolder)
    _run()



